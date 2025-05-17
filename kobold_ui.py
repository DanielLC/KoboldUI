import sys
from auto_grid_layout import *
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, QSize, QMetaObject, Signal, QRect, QEvent
from PySide6.QtGui import QIntValidator, QDoubleValidator, QUndoStack, QUndoCommand, QTextCursor, QAction, QCursor, QKeySequence, QShortcut

MARGIN = 10

class KoboldUI(QMainWindow):
    text_to_add = Signal(str)
    tab_selected = Signal(int)  # Signal for when a tab is selected
    new_tab_requested = Signal()  # Signal for when the "+" tab is clicked
    tab_renamed = Signal(int, str)  # Signal for when a tab is renamed
    send_command_requested = Signal()    # Signal when you click submit, or when you hit enter in the input field
    abort_requested = Signal()      # Signal when you click abort
    character_added = Signal()
    character_selected = Signal(QPushButton)    # Signal when a button is clicked to select a character
    mouse_over_character = Signal(str)
    character_removed_from_project = Signal(str)
    character_deleted = Signal(str)
    tab_closed = Signal(int)
    closing_program = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kobold UI")
        
        # Create stacked widget to switch between normal view and search view
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        
        # Create normal view container
        main_view = QWidget()
        main_layout = QVBoxLayout(main_view)
        
        # Create search view container
        self.search_view = QWidget()
        self.search_layout = QVBoxLayout(self.search_view)
        
        # Add both to stacked widget
        self.stacked_widget.addWidget(main_view)
        self.stacked_widget.addWidget(self.search_view)
        

        # Create tab bar
        # I'm using a QTabBar rather than a QTabWidget because I'm not actually changing the visible UI elements when a new tab is selected. It just tells the controller to change the contents of those elements.
        self.tab_bar = QTabBar()
        self.tab_bar.setDocumentMode(True)
        self.tab_bar.addTab("+")
        self.tab_bar.currentChanged.connect(self._handle_tab_changed)
        self.text_to_add.connect(self._add_text)
        self.tab_bar.tabBarDoubleClicked.connect(self._rename_tab)
        self.tab_bar.event = self._tab_bar_event
        self.tab_bar.setAttribute(Qt.WA_Hover)
        #self.tab_bar.setTabsClosable(True)
        self.setStyleSheet("""
            QTabBar::tab {
                padding: 6px 12px;
                min-width: 150px;
                min-height: 22px;
            }
            QTabBar {
                qproperty-expanding: false;
            }
            QTabBar::tab:last {
                min-width: 20px;
                padding: 6px;
            }
            QTabBar::close-button {
                visibility: hidden;
            }
            QScrollArea {
                border: none;
            }
        """)
        self.close_tab_button = QPushButton("×")
        self.close_tab_button.clicked.connect(self._remove_tab)
        self.close_tab_button.setMaximumWidth(22)
        self.close_tab_button.setMaximumHeight(22)
        self.mouse_over_tab = -1
        main_layout.addWidget(self.tab_bar)
        
        # Create main container
        main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(main_splitter)
        
        # Create the three main panels
        self.left_panel = QWidget()
        self.middle_panel = QWidget()
        self.right_panel = QWidget()
        
        main_splitter.addWidget(self.left_panel)
        main_splitter.addWidget(self.middle_panel)
        main_splitter.addWidget(self.right_panel)
        
        #This makes the handles visible, but it looks terrible.
        #main_splitter.setStyleSheet("QSplitter::handle { background-color: #999999; }")
        
        # Set initial sizes
        main_splitter.setSizes([1, 2, 1])
        main_splitter.setHandleWidth(8)
        
        # Setup each panel
        self.setup_left_panel()
        self.setup_middle_panel()
        self.setup_right_panel()
        self.setup_search_panel()
        
        self.command_entry.returnPressed.connect(self._on_command_entry_return)
        self.send_button.clicked.connect(self._on_send_button_clicked)
        
        self.is_generating = False
        
        self.edited_tab_index = -1
        
        # Create shortcuts
        self.search_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
    
    def setup_search_panel(self):
        self.project_search_bar = QLineEdit()
        self.search_layout.addWidget(self.project_search_bar, 0)
        self.search_panel_button_layout = AutoGridLayout()
        self.search_layout.addWidget(self.search_panel_button_layout, 0)
        self.search_layout.setAlignment(self.search_panel_button_layout, Qt.AlignTop)
        self.search_layout.addStretch(1)

    #TODO: I should probably change it to just pass in names, and have the controller talk directly to the auto_grid_layout.
    def project_search(self, projects):
        self.search_panel_button_layout.setButtons([project.name for project in projects])

    def setup_left_panel(self):
        layout = QVBoxLayout(self.left_panel)
        layout.setContentsMargins(MARGIN, MARGIN, 0, MARGIN)
        
        content_splitter = QSplitter(Qt.Vertical)
        
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        content_splitter.addWidget(top_widget)
        
        # Character Detail Editor
        self.char_name = QLineEdit()
        top_layout.addWidget(self.char_name)
        
        # Character Detail Editor
        self.char_detail = QTextEdit()
        self.char_detail.setPlaceholderText("Character Details")
        top_layout.addWidget(self.char_detail)
        
        # Bottom area
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        
        # Character search input
        self.character_search = QLineEdit()
        bottom_layout.addWidget(self.character_search)
        
        # Character list with scroll area
        char_list_scroll = QScrollArea()
        char_list_scroll.setWidgetResizable(True)
        char_list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        char_list_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Container for character buttons
        char_list_container = QWidget()
        self.char_list_layout = QVBoxLayout(char_list_container)
        
        # Add the + button at the top. This will only be visible while searching.
        self.add_character_button = QPushButton('+')
        self.add_character_button.hide()
        self.char_list_layout.addWidget(self.add_character_button)
        
        # Add spacer at the bottom of the character list
        self.char_list_layout.addStretch()
        
        # Set the container as the scroll area's widget
        char_list_scroll.setWidget(char_list_container)
        bottom_layout.addWidget(char_list_scroll)
        content_splitter.addWidget(bottom_widget)
        
        # Set up the menu for right clicking on character buttons
        self.character_menu = QMenu()
        self.character_menu.addAction("Remove from project", self._remove_character)
        self.character_menu.addAction("Delete character", self._delete_character)
        
        layout.addWidget(content_splitter)

    def setup_middle_panel(self):
        layout = QVBoxLayout(self.middle_panel)
        layout.setContentsMargins(0, MARGIN, 0, MARGIN)
        
        # Create a splitter for memory and story areas
        content_splitter = QSplitter(Qt.Vertical)
        
        # Memory area
        self.memory_area = QTextEdit()
        self.memory_area.setPlaceholderText("Memory Area")
        content_splitter.addWidget(self.memory_area)
        
        # Story area
        self.story_area = QTextEdit()
        self.story_area.setPlaceholderText("Story Area")
        content_splitter.addWidget(self.story_area)
        
        # Set initial sizes - story area gets more space
        content_splitter.setSizes([1, 3])
        
        layout.addWidget(content_splitter)
        
        # Bottom area for input
        bottom_widget = QWidget()
        bottom_layout = QHBoxLayout(bottom_widget)
        
        # Max tokens
        self.max_tokens_label = QLabel("Max Tokens:")
        self.max_tokens = QLineEdit()
        self.max_tokens.setValidator(QIntValidator())
        self.max_tokens.setMaximumWidth(75)
        self.max_tokens.setText("100")
        bottom_layout.addWidget(self.max_tokens_label)
        bottom_layout.addWidget(self.max_tokens)
        
        # Type selection dropdown
        self.select_type = QComboBox()
        self.select_type.addItems(["You:", ">"])
        bottom_layout.addWidget(self.select_type)
        
        # Command input field
        self.command_entry = QLineEdit()
        bottom_layout.addWidget(self.command_entry)
        
        # Send button
        self.send_button = QPushButton("Send")
        #self.send_button.clicked.connect(self.on_send)
        bottom_layout.addWidget(self.send_button)
        
        # Temperature
        self.temperature_label = QLabel("Temperature:")
        self.temperature = QLineEdit()
        non_negative_float_validator = QDoubleValidator()
        non_negative_float_validator.setBottom(0.0)
        self.temperature.setValidator(non_negative_float_validator)
        self.temperature.setMaximumWidth(75)
        self.temperature.setText("0.7")
        bottom_layout.addWidget(self.temperature_label)
        bottom_layout.addWidget(self.temperature)
        
        layout.addWidget(bottom_widget)

    def setup_right_panel(self):
        layout = QVBoxLayout(self.right_panel)
        layout.setContentsMargins(0, MARGIN, MARGIN, MARGIN)
        content_splitter = QSplitter(Qt.Vertical)
        
        # Location Detail
        self.loc_detail = QTextEdit()
        self.loc_detail.setPlaceholderText("Location Details")
        content_splitter.addWidget(self.loc_detail)
        
        # Location List with scroll
        loc_list_scroll = QScrollArea()
        loc_list_scroll.setWidgetResizable(True)
        loc_list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        loc_list_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Container for location buttons
        loc_list_container = QWidget()
        loc_list_layout = QVBoxLayout(loc_list_container)
        
        # Create location buttons
        self.location_buttons = []
        for i in range(10):
            button = QPushButton(f"Location {i+1}")
            button.clicked.connect(lambda checked, name=f"Location {i+1}", btn=button: 
                                  self.on_location_selected(name, btn))
            loc_list_layout.addWidget(button)
            self.location_buttons.append(button)
        
        # Add spacer at the bottom
        loc_list_layout.addStretch()
        
        # Set the container as the scroll area's widget
        loc_list_scroll.setWidget(loc_list_container)
        content_splitter.addWidget(loc_list_scroll)
        
        content_splitter.setSizes([1, 3])
        
        layout.addWidget(content_splitter)
    
    def closeEvent(self, event):
        self.closing_program.emit()
        event.accept()

    def set_all_tabs(self, names, index):
        old_state = self.tab_bar.blockSignals(True) # Block the signals
        
        while self.tab_bar.count() > 1:
            self.tab_bar.removeTab(0)
        for i, name in enumerate(names):
            self.tab_bar.insertTab(i, "Untitled" if name == '' else name)
        
        self.tab_bar.blockSignals(old_state)    # Unblock the signals
        self.tab_bar.setCurrentIndex(index)     # Now that the signals are unblocked, it signals that it's selecting this tab, so app_controller will populate it.

    def _on_command_entry_return(self):
        # Only send command when not generating
        if not self.is_generating:
            self.send_command_requested.emit()

    def _on_send_button_clicked(self):
        if self.is_generating:
            self.abort_requested.emit()
        else:
            self.send_command_requested.emit()

    def on_character_selected(self, button):
        button.style().polish(button)
        self.character_selected.emit(button)
    
    def set_character_active(self, button, active):
        button.setChecked(active)

    def on_location_selected(self, name, button):
        pass
    
    def get_memory(self):
        return self.memory_area.toPlainText()
    
    def set_memory(self, text):
        self.memory_area.setText(text)
    
    def get_story(self):
        return self.story_area.toPlainText()
    
    def set_story(self, text):
        self.story_area.setText(text)
    
    def set_character(self, character):
        self.char_name.setText('' if character is None else character.name)
        self.char_detail.setText('' if character is None else character.description)
    
    def get_character_description(self):
        return self.char_detail.toPlainText()
    
    def set_character_list(self, characters, active_characters = set(), is_searching = False, character_addable = False):
        # Clear existing buttons
        # But leave the + (first thing on the list) and the stretch (last thing)
        while self.char_list_layout.count() > 2:
            item = self.char_list_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        
        # Add each character using the existing method
        for character in characters:
            self._add_character(character.name, character in active_characters, is_searching)
        
        # Make the + visible if and only if you can add the current text as a character
        self.add_character_button.setVisible(character_addable)
    
    def _add_character(self, name, active, is_searching):
        button = QPushButton()
        button.setText(name)
        button.clicked.connect(lambda checked, btn=button: self.on_character_selected(btn))
        if is_searching:
            button.enterEvent = lambda event: self.mouse_over_character.emit(name)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        button.setCheckable(True)
        button.setChecked(active)
        button.setContextMenuPolicy(Qt.CustomContextMenu)
        button.customContextMenuRequested.connect(lambda pos, btn=button: self._execute_character_menu(pos, btn))
        stretch_index = self.char_list_layout.count() - 1  # Assuming stretch is last item
        self.char_list_layout.insertWidget(stretch_index, button)

    def _remove_character(self):
        print("Remove character:", self.character_menu.button.text())
        self.character_removed_from_project.emit(self.character_menu.button.text())
    
    def _delete_character(self):
        name = self.character_menu.button.text()
        reply = QMessageBox.question(
            self,
            "Confirm Action",
            f"Are you sure you want to delete {name}?\nThey’ll be removed from all projects.\nThis action cannot be undone.",
            QMessageBox.Ok | QMessageBox.Cancel
        )

        if reply == QMessageBox.Ok:
            print("Delete character:", name)
            self.character_deleted.emit(name)
    
    def _execute_character_menu(self, pos, btn):
        self.character_menu.button = btn
        self.character_menu.exec_(btn.mapToGlobal(pos))
    
    def get_and_clear_entry(self):
        text = self.command_entry.text()
        self.command_entry.setText('')
        return text
    
    def get_command_type(self):
        return self.select_type.currentText()
    
    def get_max_tokens(self):
        return int(self.max_tokens.text())
    
    def get_temperature(self):
        return float(self.temperature.text())
    
    def add_text(self, new_text):
        self.text_to_add.emit(new_text)
    
    def _add_text(self, new_text):
        cursor = self.story_area.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.story_area.setTextCursor(cursor)
        self.story_area.insertPlainText(new_text)
        QApplication.processEvents()
    
    def _handle_tab_changed(self, index):
        if self.edited_tab_index >= 0:
            self._finish_edit()
        if index == self.tab_bar.count() - 1:   #If it's the + tab
            self.new_tab_requested.emit()
        else:
            self.tab_selected.emit(index)
            
            # self.tab_bar.setTabButton(self.current_tab, QTabBar.RightSide, None)
            # self.current_tab = index
            # self.tab_bar.setTabButton(index, QTabBar.RightSide, self.close_tab_button)
    
    def _tab_bar_event(self, event):
        if event.type() in (QEvent.HoverEnter, QEvent.HoverMove, QEvent.HoverLeave):
            self._tab_hover(event.pos())
        return QTabBar.event(self.tab_bar, event)
    
    def _tab_hover(self, pos):
        oldIndex = self.mouse_over_tab
        newIndex = self.tab_bar.tabAt(pos)
        if newIndex == self.tab_bar.count() - 1:
            newIndex = -1
        if oldIndex == newIndex:
            return
        if oldIndex != -1:
            self.tab_bar.setTabButton(oldIndex, QTabBar.RightSide, None)
        self.mouse_over_tab = newIndex
        if newIndex != -1:
            self.tab_bar.setTabButton(newIndex, QTabBar.RightSide, self.close_tab_button)
    
    def lock_story_area(self, locked = True):
        print("Locking story area")
        self.story_area.setReadOnly(locked)
        QApplication.processEvents()    #TODO: Do I need this?
    
    def set_generating_state(self, locked = True):
        print("Setting generating state.")
        self.is_generating = locked
        self.send_button.setText("Abort" if locked else "Send")
    
    def new_tab(self, name):
        print("New tab")
        last = self.tab_bar.count() - 1
        self.tab_bar.insertTab(last, '')
        #TODO: Should I be trying to avoid redundant code here?
        self.set_tab_name(last, name)
        self.tab_bar.setCurrentIndex(last)
    
    def _remove_tab(self):
        last = self.tab_bar.count() - 2
        # If you're selecting the last tab and close it, it ends with the '+' tab selected, which automatically opens a new tab.
        # But if that's the only tab left, it really should automatically make a new tab. So let's just select a different one.
        if last == self.mouse_over_tab == self.tab_bar.currentIndex() > 0:
            self.tab_bar.setCurrentIndex(last-1)
        # if self.tab_bar.tabText(self.mouse_over_tab) == "Untitled":
            # reply = QMessageBox.question(
                # self,
                # "Confirm Action",
                # f"Are you sure you want to close this tab?\nUntitled tabs are deleted when closed.\nThis action cannot be undone.",
                # QMessageBox.Ok | QMessageBox.Cancel
            # )

            # if reply != QMessageBox.Ok:
                # return
        self.tab_closed.emit(self.mouse_over_tab)
    
    def remove_tab(self, index):
        self.tab_bar.setTabButton(index, QTabBar.RightSide, None)   #Since I'm just using one close button, I need to remove it before I close the tab or it will disappear.
        self.tab_bar.removeTab(index)
    
    def _rename_tab(self, index):
        if index == -1 or index == self.tab_bar.count() - 1:
            return
        
        self.edited_tab_index = index
        original_text = self.tab_bar.tabText(index)
        if original_text == "Untitled":
            original_text = ""
        self.tab_bar.setTabText(index, "")
        
        # Create line edit
        self.tab_name_edit = QLineEdit(original_text)
        self.tab_name_edit.setFrame(False)
        
        # Position the line edit directly over the tab
        tab_rect = self.tab_bar.tabRect(index)
        self.tab_name_edit.setParent(self.tab_bar)
        # Add margins to the rectangle
        x_margin = 10
        y_margin = 5
        adjusted_rect = QRect(
            tab_rect.x() + x_margin,
            tab_rect.y() + y_margin,
            tab_rect.width() - (x_margin * 2),
            tab_rect.height() - (y_margin * 2)
        )
        self.tab_name_edit.setGeometry(adjusted_rect)
        self.tab_name_edit.show()
        
        self.tab_name_edit.selectAll()
        self.tab_name_edit.setFocus(Qt.MouseFocusReason)
        
        self.tab_name_edit.editingFinished.connect(self._finish_edit)
        self.tab_name_edit.focusOutEvent = lambda event: (self._finish_edit(), QLineEdit.focusOutEvent(self.tab_name_edit, event))
    
    def _finish_edit(self):
        self.tab_name_edit.deleteLater()
        self.tab_renamed.emit(self.edited_tab_index, self.tab_name_edit.text().strip())
    
    def set_tab_name(self, index, name):
        self.tab_bar.setTabText(index, "Untitled" if name == '' else name)
        self.edited_tab_index = -1
    
    def create_window():
        app = QApplication(sys.argv)
        window = KoboldUI()
        window.app = app
        window.showMaximized()
        return window
    
    def run_app(self):
        return self.app.exec()

if __name__ == "__main__":
    window = create_window()
    sys.exit(window.app.exec())