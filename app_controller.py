import sys
from kobold_ui import KoboldUI
from narrative_data import *
from PySide6.QtWidgets import QInputDialog, QLineEdit
import kobold_api
import subprocess
import time
import threading
import time
from fnmatch import fnmatch
import json

BASE_TYPING_TIME = 0.2
TYPING_TIME_MULTIPLIER = 0.9

class Controller:
    def __init__(self):
        # Create UI
        self.ui = KoboldUI.create_window()
        
        # Setup event handlers/listeners for UI elements
        self.setup_ui_handlers()
        
        #self.wordcount = 0
        #self.letter_delay = 0.01
        #self.generating is the story that's generating, or None if there isn't one. It's not the index, because tabs could be closed mid-generation messing it up. It's the object itself.
        self.generating = None
        self.aborting = False
        self.generated_text = ""
        self._typing_thread = None
        self.searching_character = False
        self.wake_thread = threading.Event()
        self.typing_thread = threading.Thread(target=self._typing_loop, daemon=True)
        self.typing_thread.start()
        self.lock = threading.Lock()
        
        self.project = None
        self.load()
        
    #TODO: I should probably change all the text stuff to happen on editing finished.
    def setup_ui_handlers(self):
        self.ui.send_command_requested.connect(self.handle_send)
        self.ui.abort_requested.connect(self.handle_abort)
        self.ui.tab_selected.connect(self.select_tab)
        self.ui.new_tab_requested.connect(self.new_tab)
        self.ui.memory_area.textChanged.connect(self.update_memory)
        self.ui.story_area.textChanged.connect(self.update_story)
        self.ui.tab_renamed.connect(self.rename_tab)
        self.ui.tab_closed.connect(self.close_tab)
        self.ui.char_detail.textChanged.connect(self.update_character_data)
        self.ui.char_name.editingFinished.connect(self.update_character_name)
        self.ui.character_selected.connect(self.handle_character_selected)
        self.ui.character_search.textChanged.connect(self.character_search)
        self.ui.mouse_over_character.connect(self.character_hover)
        self.ui.add_character_button.clicked.connect(self.add_character)
        self.ui.character_removed_from_project.connect(self.remove_character_from_project)
        self.ui.character_deleted.connect(self.delete_character)
        self.ui.closing_program.connect(self.save)   #TODO: There should be a way to close without saving.
        self.ui.search_shortcut.activated.connect(self.project_search)
        self.ui.search_panel_button_layout.button_clicked.connect(self.project_search_button_clicked)
        self.ui.project_search_bar.textChanged.connect(self.project_filter)
    
    #TODO: I should probably change this to just pass in names. Either that or make the buttons actually track the projects.
    #Also, this is very similar to character_search()
    def project_search(self):
        self.ui.stacked_widget.setCurrentIndex(1)
        self.project_filter()
    
    def project_filter(self):
        if self.ui.stacked_widget.currentIndex() != 1:
            return
        text = self.ui.project_search_bar.text().strip()
        pattern = f"*{text.lower()}*"
        #TODO If I'm looking at the keys, I don't need to to be lowercase.
        matching_projects = [
            project for name, project in Project.named_projects.items()
            if fnmatch(name, pattern)
        ]
        self.ui.project_search(matching_projects)

    def handle_abort(self):
        self.aborting = True
        kobold_api.abort()
    
    def handle_send(self):
        self.ui.lock_story_area(True)
        self.ui.set_generating_state(True)
        self.generating = self.project
        self.completing = False
        # Process input and interact with the LLM
        memory = self.ui.get_memory().strip()
        #Add in all the characters. It might be better to use join() with the memory and characters.
        for character in self.project.active_characters:
            description = character.description
            if description != '':
                memory += '\n\n' + description
        memory += '\n\n'
        story = self.ui.get_story().strip()
        max_tokens = self.ui.get_max_tokens()
        temperature = self.ui.get_temperature()
        entry = self.ui.get_and_clear_entry()
        command_type = self.ui.get_command_type()
        if entry != '':
            if story != '':
                story += '\n\n'
            story += f"{command_type} {entry.strip()}\n\n"
            self.ui.set_story(story)
        self.extra_length = 0
        #kobold_api.prompt(self.update_story, story, memory, stopSequence = [command_type])
        #kobold_api.stream_prompt(self.update_story_simple, story, memory, stopSequence = [command_type])
        threading.Thread(
            target=lambda: kobold_api.stream_prompt(self.update_story_smooth, story, memory, max_tokens, temperature, stopSequence = [command_type]),
            daemon=True
        ).start()

    def update_story_simple(self, extra, completed):
        self.ui.add_text(extra, completed)

    def update_story_smooth(self, extra, completed):
        with self.lock:
            self.generated_text += extra
            self.completing = completed
            self.wake_thread.set()
    
    def add_text(self, text, completed):
        self.generating.story += text
        is_cur_story = self.generating is self.project
        if is_cur_story:
            self.ui.add_text(text)
        if completed:
            self.ui.set_generating_state(False)
            if is_cur_story:
                self.ui.lock_story_area(False)
            self.generating = None

    def _typing_loop(self):
        index = 0
        typing_time = 0
        wait_time = None
        while True:
            interrupted = self.wake_thread.wait(wait_time)
            self.wake_thread.clear()
            with self.lock:
                #I need to make sure this works for all the cases:
                #1. (Done) It just recieved the first token.
                #2. (Done) It recieved another token while in the middle of typing, and needs to update based on how long it waited so far.
                #3. (Done) It recieved the last token, and needs to type quickly and then
                    #3b. (Done) Alert the main thread that typing is completed and the text box can be unlocked.
                #4. (Done) It's aborting, and must type the whole buffer.
                #5. (Done) The wait_time completed and it's time to write the next letter.
                
                #The user clicked abort. Time to flush all the text.
                if self.aborting:
                    self.add_text(self.generated_text[index:], self.completing)
                    index = len(self.generated_text)
                    wait_time = None
                    if self.completing:
                        index = 0
                        self.generated_text = ''
                        self.aborting = False
                    continue
                #It recieved another token in the middle of typing. Update the wait times, but don't actually do anything. If it needs to immediatly type something, wait_time will be negative. I guess I could have it fall through, but this seems cleaner.
                elif interrupted and wait_time is not None:
                    new_time = time.monotonic()
                    elapsed_time = new_time - start_time
                    remaining_text = len(self.generated_text) - index
                    typing_time = BASE_TYPING_TIME / remaining_text
                    wait_time = typing_time - elapsed_time
                    continue
                #It finished typing the letter or it recieved the first token.
                else:
                    #If this is the first token, there's no lower bound for how fast to type, so set prev_duration to zero. Otherwise, calculate prev_duration based on when the last token was typed.
                    if wait_time == None:
                        prev_duration = 0
                        start_time = time.monotonic()
                    else:
                        new_time = time.monotonic()
                        prev_duration = new_time - start_time
                        #print(f"prev_duration: {prev_duration}")
                        start_time = new_time
                    remaining_text = len(self.generated_text) - index
                    #This line feels really weird. I print the letter at index, and then check if it's the last one. Except remaining_text is still 1, since that's the letter I just wrote. Then I increment index and decrement remaining_text. It feels like I should move this, but then I'd have to do something weirder use self.generated_text[index-1].
                    self.add_text(self.generated_text[index], self.completing and remaining_text == 1)
                    index += 1
                    remaining_text -= 1
                    #print(f"Remaining text: {remaining_text}")
                    #If there's no text left, set the wait time to None (wait forever).
                    if remaining_text == 0:
                        wait_time = None
                        if self.completing:
                            print("Completed.")
                            index = 0
                            self.generated_text = ''
                        else:
                            print("Ran out of text. Waiting for next token.")
                    #Otherwise, if this is the last token, set the wait time to a bit faster than the last one (finish quickly).
                    elif self.completing:
                        wait_time = typing_time * TYPING_TIME_MULTIPLIER
                        #print(f"Completing. Current letter: {self.generated_text[index-1]}, wait_time: {wait_time}")
                    #Otherwise, set it to base time/remaining (so the more is in the buffer the faster it types) but cap it at a bit faster than the last one.
                    else:
                        wait_time = max(BASE_TYPING_TIME / remaining_text, typing_time * TYPING_TIME_MULTIPLIER)
                    typing_time = 0 if wait_time is None else wait_time
                    continue
    
    def add_character(self):
        name = self.ui.character_search.text().strip()
        if not self.is_char_name_valid(name):
            print(f"Error: name '{name}' is not valid. The + button shouldn't be there. But if this function (app_controller.Controller.add_character()) runs, that means you somehow clicked it anyway.")
            return
        new_character = Character(name)
        Project.all_characters[name.lower()] = new_character
        self.project.project_characters.add(new_character)
        self.project.active_characters.add(new_character)
        self.set_selected_character(new_character)
        self.ui.character_search.setText('')    #This automatically calls the function here for searching for the name, which means it brings you back to seeing all the characters.
    
    def remove_character_from_project(self, name):
        character = Project.all_characters[name.lower()]
        self.project.project_characters.discard(character)
        self.project.active_characters.discard(character)
        self._update_character_buttons()
    
    def delete_character(self, name):
        name = name.lower()
        character = Project.all_characters[name]
        self.project.project_characters.discard(character)
        self.project.active_characters.discard(character)
        if self.project.selected_character == character:
            self.project.selected_character = None
            self.ui.set_character(None)
        del Project.all_characters[name]
        self._update_character_buttons()
    
    def handle_character_selected(self, button):
        name_lower = button.text().lower()
        print("handle_character_selected:", name_lower)
        if self.searching_character:
            #Pool is whatever them being selected means right now. If you're searching, it's any character in your project.
            pool = self.project.project_characters
            clicked_character = Project.all_characters[name_lower]
            active = clicked_character not in pool
            if active:
                pool.add(clicked_character)
                #If you're adding it to the project, you probably want it in the scene
                self.project.active_characters.add(clicked_character)
            else:
                pool.remove(clicked_character)
                #If you're removing it from the project, remove it if it's also in the scene
                self.project.active_characters.discard(clicked_character)
            self.ui.set_character_active(button, active)

        else:
            clicked_character = Project.all_characters[name_lower]
            self.project.selected_character = clicked_character
            self.ui.set_character(clicked_character)
            #If you're not searching, it's just the active characters.
            pool = self.project.active_characters
            active = clicked_character not in pool
            if active:
                pool.add(clicked_character)
            else:
                pool.remove(clicked_character)
            self.ui.set_character_active(button, active)
    
    #This runs if you hover over a character during a search. It sets them to the selected character. But it doesn't change whether or not they're active or in the project.
    def character_hover(self, name):
        self.project.selected_character = Project.all_characters[name.lower()]
        self.ui.set_character(self.project.selected_character)
    
    def update_character_name(self):
        #This if statement only runs if you try to edit the name when there's no character selected. I should probably make that not allowed.
        if self.project.selected_character == None:
            return
        old_name = self.project.selected_character.name
        new_name = self.ui.char_name.text().strip()
        if not self.is_char_name_valid(new_name):
            self.ui.char_name.setText(old_name)
            return
        self.project.selected_character.name = new_name
        del Project.all_characters[old_name.lower()]
        Project.all_characters[new_name.lower()] = self.project.selected_character
        self._update_character_buttons()
    
    def update_character_data(self):
        #If no character is selected, don't do anything.
        #TODO: Maybe it should hide the window entirely.
        if self.project.selected_character is None:
            return
        #If I change this to use a Character class, then it would look more like:
        #self.project.selected_character.detail = character_detail
        self.project.selected_character.description = self.ui.get_character_description()
    
    def set_selected_character(self, character):
        self.project.selected_character = character
        self.ui.set_character(character)
    
    #This just runs characer_search() with whatever the text of the search is.
    def _update_character_buttons(self):
        self.character_search(self.ui.character_search.text())
    
    def is_char_name_valid(self, name):
        return name.lower() not in Project.all_characters and name != '+'
    
    #TODO: I should probably make it so if you type multiple words, it searches for something with all the words but not necessarily the whole string in order. And maybe make it search details instead of just names.
    def character_search(self, text):
        text = text.strip()
        self.searching_character = text != ''
        #If the search bar is empty, then just show the characters list for the projgect. It's not searching.
        if not self.searching_character:
            self.ui.set_character_list(self.project.project_characters, self.project.active_characters, False, False)
            return
        pattern = f"*{text.lower()}*"
        #TODO If I'm looking at the keys, I don't need to to be lowercase.
        matching_names = [
            character for name, character in Project.all_characters.items()
            if fnmatch(name, pattern)
        ]
        self.ui.set_character_list(matching_names, set(self.project.project_characters), True, self.is_char_name_valid(text))
    
    def run(self):
        # self.start_kobold()   # This line would make it more convenient to run, but is really inconvenient for testing unless I make a way to check if it's already running.
        # Show the UI
        # Start the application event loop
        return self.ui.run_app()
    
    #If you change it to actually run this code, make sure to add in the model path.
    def start_kobold(self):
        # Launch kobold.cpp as a subprocess
        self.kobold_process = subprocess.Popen(
            ["../koboldcpp_cu12.exe", "Model path here"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        ready_line = r"Please connect to custom endpoint at http://localhost:5001"
        
        for line in self.kobold_process.stdout:
            #print("Kobold:", line.strip())
            
            # Check if this line indicates kobold is ready
            if line.startswith(ready_line):
                return
    
    def project_search_button_clicked(self, button):
        name = button.text()
        project = Project.named_projects[name.lower()]
        print("app_controlly.py setting project to", name)
        if project in Project.open_projects:
            i = Project.open_projects.index(project)
        else:
            i = len(Project.open_projects)
            Project.open_projects.append(project)
            self.ui.new_tab(project.name)
        self.ui.stacked_widget.setCurrentIndex(0)
        self.ui.project_search_bar.setText('')
        self.ui.tab_bar.setCurrentIndex(i)

    def populate_gui(self, project):
        self.ui.set_memory(project.memory)
        self.ui.set_story(project.story)
        self.ui.set_character_list(project.project_characters, project.active_characters)
        self.ui.set_character(project.selected_character)
        #print(project.name, project.project_characters)
    
    def save(self):
        with open("save.json", "w") as outfile:
            json.dump(Project.all_to_dictionary(), outfile, indent = 4)
    
    def load(self):
        try:
            with open('save.json', 'r') as openfile:
                Project.load_from_dictionary(json.load(openfile))
            print("File found and loaded.")
        except FileNotFoundError:
            print("Savefile not found. Creating a new save.")
            Project.start_empty()
        self.ui.set_all_tabs([project.name for project in Project.open_projects], Project.story_index)
    
    def select_tab(self, i):
        if self.generating is self.project:
            self.ui.lock_story_area(False)
        Project.story_index = i
        self.project = Project.open_projects[i]
        self.populate_gui(self.project)
        if self.generating is self.project:
            self.ui.lock_story_area(True)
    
    def update_memory(self):
        self.project.memory = self.ui.get_memory()
    
    def new_tab(self):
        Project.open_projects.append(Project())
        self.ui.new_tab('')
    
    #TODO: The name is too close to update_story_smooth. I'll need to change names to clarify update_story_smooth updating it in the UI vs update_story updating it from the UI to the model.
    def update_story(self):
        self.project.story = self.ui.get_story()
    
    def _is_project_name_valid(self, name):
        name = name.lower()
        if name == '+' or name == "untitled":
            return False
        for project_name in Project.named_projects:
            if name == project_name:
                return False
        return True
    
    def rename_tab(self, index, name):
        old_name = self.project.name
        name = name.strip()
        if self._is_project_name_valid(name):
            if old_name != '':
                del Project.named_projects[old_name.lower()]
            self.project.name = name
            Project.named_projects[name.lower()] = self.project
            self.ui.set_tab_name(index, name)
        else:
            self.ui.set_tab_name(index, old_name)
    
    def close_tab(self, index):
        del Project.open_projects[index]
        self.ui.remove_tab(index)

# Application entry point
if __name__ == "__main__":
    controller = Controller()
    sys.exit(controller.run())