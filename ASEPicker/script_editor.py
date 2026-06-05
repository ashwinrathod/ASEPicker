# ASEPicker/script_editor.py
try:
    from PySide2 import QtWidgets, QtGui, QtCore
except ImportError:
    from PySide6 import QtWidgets, QtGui, QtCore

class ScriptHighlighter(QtGui.QSyntaxHighlighter):
    """Handles syntax highlighting for both Python and MEL."""
    def __init__(self, document):
        super(ScriptHighlighter, self).__init__(document)
        self.language = "python"
        self._setup_formats()
        self._setup_rules()

    def _setup_formats(self):
        self.fmt_keyword = QtGui.QTextCharFormat()
        self.fmt_keyword.setForeground(QtGui.QColor("#ff79c6")) # Pink
        self.fmt_keyword.setFontWeight(QtGui.QFont.Bold)

        self.fmt_string = QtGui.QTextCharFormat()
        self.fmt_string.setForeground(QtGui.QColor("#f1fa8c")) # Yellow

        self.fmt_comment = QtGui.QTextCharFormat()
        self.fmt_comment.setForeground(QtGui.QColor("#6272a4")) # Muted Blue/Grey
        self.fmt_comment.setFontItalic(True)

        self.fmt_func = QtGui.QTextCharFormat()
        self.fmt_func.setForeground(QtGui.QColor("#50fa7b")) # Green

    def set_language(self, lang):
        lang = lang.lower()
        if getattr(self, "language", "") == lang: return 
        self.language = lang
        self._setup_rules()
        self.rehighlight()

    def _setup_rules(self):
        self.rules = []
        # Strings (Single and Double Quotes)
        self.rules.append((r'"[^"\\]*(\\.[^"\\]*)*"', self.fmt_string))
        self.rules.append((r"'[^'\\]*(\\.[^'\\]*)*'", self.fmt_string))

        # Function calls
        self.rules.append((r'\b[A-Za-z0-9_]+(?=\()', self.fmt_func))

        # Keywords & Comments depending on Language
        if self.language == "python":
            kws = ["def", "class", "import", "from", "return", "if", "else", "elif", "for", "while", "in", "try", "except", "print", "and", "or", "not", "True", "False", "None", "self", "pass", "global", "exec"]
            self.rules.append((r'#[^\n]*', self.fmt_comment))
        else: # MEL
            kws = ["global", "proc", "if", "else", "while", "for", "in", "return", "break", "continue", "int", "float", "string", "vector", "matrix"]
            self.rules.append((r'//[^\n]*', self.fmt_comment))

        for kw in kws:
            self.rules.append((r'\b' + kw + r'\b', self.fmt_keyword))

    def highlightBlock(self, text):
        for pattern_str, format in self.rules:
            if hasattr(QtCore, 'QRegularExpression'):
                # PySide6 (Maya 2025+) uses QRegularExpression
                expression = QtCore.QRegularExpression(pattern_str)
                match_iterator = expression.globalMatch(text)
                while match_iterator.hasNext():
                    match = match_iterator.next()
                    self.setFormat(match.capturedStart(), match.capturedLength(), format)
            else:
                # PySide2 (Maya 2024 and older) uses QRegExp
                expression = QtCore.QRegExp(pattern_str)
                index = expression.indexIn(text)
                while index >= 0:
                    length = expression.matchedLength()
                    self.setFormat(index, length, format)
                    index = expression.indexIn(text, index + length)

class ScriptEditorWidget(QtWidgets.QTextEdit):
    """A custom text editor for coding, replacing tabs with 4 spaces."""
    def __init__(self, parent=None):
        super(ScriptEditorWidget, self).__init__(parent)
        
        font = QtGui.QFont("Consolas", 10)
        font.setStyleHint(QtGui.QFont.Monospace)
        self.setFont(font)
        
        self.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; border: 1px solid #444; border-radius: 4px;")
        self.setAcceptRichText(False)
        self.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)
        
        self.highlighter = ScriptHighlighter(self.document())

    def set_language(self, lang):
        self.highlighter.set_language(lang)

    def keyPressEvent(self, event):
        # Override Tab key to insert 4 spaces for strict Python formatting
        if event.key() == QtCore.Qt.Key_Tab:
            self.insertPlainText("    ")
            return
        QtWidgets.QTextEdit.keyPressEvent(self, event)

class ExpandedScriptEditor(QtWidgets.QDialog):
    """A floating, resizable window for editing large scripts."""
    def __init__(self, parent=None, initial_text="", lang="python"):
        super(ExpandedScriptEditor, self).__init__(parent)
        self.setWindowTitle("Advanced Script Editor")
        self.resize(800, 600)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowMaximizeButtonHint)
        
        lay = QtWidgets.QVBoxLayout(self)
        self.editor = ScriptEditorWidget()
        self.editor.set_language(lang)
        self.editor.setPlainText(initial_text)
        
        # Add test button
        btn_lay = QtWidgets.QHBoxLayout()
        self.btn_test = QtWidgets.QPushButton("Run / Test Script")
        self.btn_test.setStyleSheet("background-color: #3a5f43; font-weight: bold; padding: 6px;")
        self.btn_test.clicked.connect(self.test_script)
        
        self.btn_save = QtWidgets.QPushButton("Apply & Close")
        self.btn_save.setStyleSheet("background-color: #5285a6; font-weight: bold; padding: 6px;")
        self.btn_save.clicked.connect(self.accept)
        
        self.btn_cancel = QtWidgets.QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_lay.addWidget(self.btn_test)
        btn_lay.addStretch()
        btn_lay.addWidget(self.btn_cancel)
        btn_lay.addWidget(self.btn_save)
        
        lay.addWidget(self.editor)
        lay.addLayout(btn_lay)
        
    def test_script(self):
        cmd = self.editor.toPlainText()
        cmd_type = self.editor.highlighter.language
        if not cmd.strip(): return
        try:
            if cmd_type == "mel":
                import maya.mel as mel
                mel.eval(cmd)
            else:
                exec(cmd, globals())
        except Exception as e:
            print(f"ASEPicker Script Test Error: {e}")