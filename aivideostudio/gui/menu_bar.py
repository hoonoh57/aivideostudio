from PyQt6.QtGui import QAction


def create_menu_bar(window):
    mb = window.menuBar()
    fm = mb.addMenu("File(&F)")
    for t, s in [("New", "Ctrl+N"), ("Open", "Ctrl+O"), ("Save", "Ctrl+S"),
                 ("Import", "Ctrl+I"), ("Export", "Ctrl+Shift+E"), ("Exit", "Alt+F4")]:
        a = QAction(t, window)
        a.setShortcut(s)
        fm.addAction(a)
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
    am = mb.addMenu("AI(&A)")
    for t in ["Auto Subtitle", "AI Voice", "BG Remove", "Upscale", "Auto Short"]:
        am.addAction(QAction(t, window))
    hm = mb.addMenu("Help(&H)")
    hm.addAction(QAction("About", window))
    return {"undo": undo_action, "redo": redo_action}
