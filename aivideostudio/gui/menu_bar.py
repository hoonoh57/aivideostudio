from PySide6.QtGui import QAction


def create_menu_bar(window):
    mb = window.menuBar()

    # File menu
    fm = mb.addMenu("File(&F)")
    act_new = QAction("New", window)
    act_new.setShortcut("Ctrl+N")
    fm.addAction(act_new)

    act_open = QAction("Open...", window)
    act_open.setShortcut("Ctrl+O")
    fm.addAction(act_open)

    fm.addSeparator()

    act_save = QAction("Save", window)
    act_save.setShortcut("Ctrl+S")
    fm.addAction(act_save)

    act_save_as = QAction("Save As...", window)
    act_save_as.setShortcut("Ctrl+Shift+S")
    fm.addAction(act_save_as)

    fm.addSeparator()

    act_import = QAction("Import Media...", window)
    act_import.setShortcut("Ctrl+I")
    fm.addAction(act_import)

    act_export = QAction("Export...", window)
    act_export.setShortcut("Ctrl+Shift+E")
    fm.addAction(act_export)

    fm.addSeparator()

    act_exit = QAction("Exit", window)
    act_exit.setShortcut("Alt+F4")
    act_exit.triggered.connect(window.close)
    fm.addAction(act_exit)

    # Connect file actions (deferred — MainWindow sets up methods after menu)
    act_new.triggered.connect(lambda: window._new_project() if hasattr(window, '_new_project') else None)
    act_open.triggered.connect(lambda: window._open_project() if hasattr(window, '_open_project') else None)
    act_save.triggered.connect(lambda: window._save_project() if hasattr(window, '_save_project') else None)
    act_save_as.triggered.connect(lambda: window._save_project_as() if hasattr(window, '_save_project_as') else None)

    # Edit menu
    em = mb.addMenu("Edit(&E)")
    undo_action = QAction("Undo", window)
    undo_action.setShortcut("Ctrl+Z")
    em.addAction(undo_action)
    redo_action = QAction("Redo", window)
    redo_action.setShortcut("Ctrl+Y")
    em.addAction(redo_action)
    for t, s in [("Cut", "Ctrl+X"), ("Copy", "Ctrl+C"), ("Paste", "Ctrl+V")]:
        a = QAction(t, window)
        a.setShortcut(s)
        em.addAction(a)

    # AI menu
    am = mb.addMenu("AI(&A)")
    for t in ["Auto Subtitle", "AI Voice", "BG Remove", "Upscale", "Auto Short"]:
        am.addAction(QAction(t, window))

    # Help menu
    hm = mb.addMenu("Help(&H)")
    hm.addAction(QAction("About", window))

    return {"undo": undo_action, "redo": redo_action}