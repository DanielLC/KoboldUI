from PySide6.QtWidgets import (QScrollArea, QWidget, QGridLayout, 
                           QSizePolicy, QVBoxLayout, QPushButton)
from PySide6.QtCore import Qt, QSize, Signal, Slot


class AutoGridLayout(QScrollArea):
    """
    A scrollable grid layout that automatically arranges child widgets
    in a grid based on available width.
    """
    
    button_clicked = Signal(QPushButton)
    
    def __init__(self, parent=None, min_width=250, height=25, 
                spacing=5, margin=5):
        """
        Initialize the auto grid layout.
        
        Args:
            parent: Parent widget
            min_width: Minimum width of each grid cell
            height: Fixed height of each grid cell
            spacing: Spacing between cells
            margin: Margin around the grid
        """
        super().__init__(parent)
        
        # Store layout parameters
        self.min_width = min_width
        self.height = height
        self.spacing = spacing
        self.margin = margin
        
        # Create container widget and layout
        self.container = QWidget()
        self.grid_layout = QGridLayout(self.container)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Configure grid layout
        self.grid_layout.setSpacing(spacing)
        self.grid_layout.setContentsMargins(margin, margin, margin, margin)
        
        # Configure scroll area
        self.setWidgetResizable(True)
        self.setWidget(self.container)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Store widgets
        self.widgets = []
        
        # Set size policy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        
        # Set initial columns
        self.prev_columns = 0
        
    # I'm not using this, and I'd rather not test it to make sure it works.
    # def addWidget(self, widget):
        # """
        # Add a widget to the grid layout.
        
        # Args:
            # widget: Widget to add
        # """
        # # Store widget
        # self.widgets.append(widget)
        
        # # Set fixed size for the widget
        # widget.setFixedSize(QSize(self.min_width, self.height))
        
        # # Update layout
        # self.updateLayout()
        
        # return widget
    
    def addButtons(self, names):
        """
        Add multiple widgets to the grid layout.
        
        Args:
            names: List of text on buttons to add
        """
        for name in names:
            button = QPushButton(name)
            button.clicked.connect(lambda event, b=button: self.button_clicked.emit(b))
            self.widgets.append(button)
        
        # Update layout once after adding all widgets
        self.updateLayout(True)
    
    def clear(self):
        """Clear all widgets from the layout."""
        # Remove widgets from layout
        for widget in self.widgets:
            self.grid_layout.removeWidget(widget)
            widget.setParent(None)
        
        self.widgets = []
    
    def setButtons(self, names):
        """
        Replaces all the widgets with the list passed in
        
        Args:
            names: List of text on buttons to add
        """
        self.clear()
        self.addButtons(names)
    
    def resizeEvent(self, event):
        """Handle resize events to update the layout."""
        super().resizeEvent(event)
        self.updateLayout(False)
    
    def updateLayout(self, force_update = False):
        """Recalculate and update the grid layout."""
        if not self.widgets:
            return
            
        # Calculate number of columns based on available width
        available_width = self.viewport().width() - 2 * self.margin
        num_columns = max(1, available_width // (self.min_width + self.spacing))
        if num_columns != self.prev_columns or force_update:
            print(num_columns, "column(s)")
            
            # Remove all widgets from layout
            for i in range(self.grid_layout.count()):
                self.grid_layout.itemAt(0).widget().setParent(None)
            
            # Add widgets to grid
            for i, widget in enumerate(self.widgets):
                row = i // num_columns
                col = i % num_columns
                self.grid_layout.addWidget(widget, row, col)
                # Calculate equal column width
                
            # Calculate total height needed
            # TODO: This should also track the number of rows and change if that changes. Or have some way of forcing an update for rewriting the grid.
            total_rows = (len(self.widgets) + num_columns - 1) // num_columns
            total_height = total_rows * (self.height + self.spacing) + 2 * self.margin
        
            # Set minimum height for the container
            # print("Setting minimum height:", total_height)
            self.setMinimumHeight(total_height)
        
        if num_columns > self.prev_columns:
            # Make sure any newly added columns can stretch.
            for col in range(self.prev_columns, num_columns):
                self.grid_layout.setColumnStretch(col, 1)
        else:
            # Set any columns that are no longer there to not stretch, and be zero-width.
            for col in range(num_columns, self.prev_columns):
                self.grid_layout.setColumnStretch(col, 0)
        
        # Emit layout changed signal
        self.prev_columns = num_columns
    
    # def sizeHint(self):
        # """Return a suggested size for the widget."""
        # return QSize(500, 300)  # Default size hint
    
    # def setMinCellWidth(self, width):
        # """Set the minimum width of cells."""
        # self.min_width = width
        # for widget in self.widgets:
            # widget.setMinimumSize(self.min_width, self.height)
            # widget.setMaximumHeight(self.height)
            # widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # self.updateLayout()
    
    # def setCellHeight(self, height):
        # """Set the height of cells."""
        # self.height = height
        # for widget in self.widgets:
            # widget.setFixedSize(QSize(self.min_width, self.height))
        # self.updateLayout()
    
    def setSpacing(self, spacing):
        """Set spacing between cells."""
        self.spacing = spacing
        self.grid_layout.setSpacing(spacing)
        self.updateLayout()
    
    def setMargin(self, margin):
        """Set margin around the grid."""
        self.margin = margin
        self.grid_layout.setContentsMargins(margin, margin, margin, margin)
        self.updateLayout()
