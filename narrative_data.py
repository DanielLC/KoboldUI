import traceback

class Character:
    def __init__(self, name, description=''):
        self.name = name
        self.description = description
        #Add tokens
    def from_dictionary(dictionary):
        return Character(dictionary['name'], dictionary['description'])
    def to_dictionary(self):
        return {'name':self.name, 'description':self.description}

class Project:
    named_projects = {}
    open_projects = []
    all_characters = {}
    max_tokens = 100
    temperature = 0.7
    story_index = 0
    
    def __init__(self):
        self.name = ''
        self.memory = ''
        self.story = ''
        self.project_characters = set()
        self.active_characters = set()
        self.selected_character = None
    
    def from_dictionary(dictionary):
        project = Project()
        project.name = dictionary['name']
        project.memory = dictionary['memory']
        project.story = dictionary['story']
        project.project_characters = set(Project.all_characters[name] for name in dictionary['project_characters'])
        project.active_characters = set(Project.all_characters[name] for name in dictionary['active_characters'])
        name = dictionary['selected_character']
        project.selected_character = None if name == '' else Project.all_characters[name]
        return project
    
    def to_dictionary(self):
        return {
            'name': self.name,
            'memory': self.memory,
            'story': self.story,
            'project_characters': [character.name.lower() for character in self.project_characters],
            'active_characters': [character.name.lower() for character in self.active_characters],
            'selected_character': '' if self.selected_character is None else self.selected_character.name.lower(),
        }
    
    def load_from_dictionary(dictionary):
        #all_characters must be read first since those characters are loaded into the other variables.
        Project.all_characters = {name:Character.from_dictionary(char_dict) for name, char_dict in dictionary['all_characters'].items()}
        Project.named_projects = {name:Project.from_dictionary(project_dict) for name, project_dict in dictionary['named_projects'].items()}
        Project.open_projects = [Project.named_projects[project_dict] if isinstance(project_dict, str) else Project.from_dictionary(project_dict) for project_dict in dictionary['open_projects']]
        Project.max_tokens = dictionary['max_tokens']
        Project.temperature = dictionary['temperature']
        Project.story_index = dictionary['story_index']
    
    def all_to_dictionary():
        myDict = {
            'named_projects': {name: project.to_dictionary() for name, project in Project.named_projects.items()},
            'open_projects': [project.to_dictionary() if project.name == '' else project.name.lower() for project in Project.open_projects],
            'all_characters': {name: character.to_dictionary() for name, character in Project.all_characters.items()},
            'max_tokens': Project.max_tokens,
            'temperature': Project.temperature,
            'story_index': Project.story_index,
        }
        return myDict