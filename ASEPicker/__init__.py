def launch():
    from . import main
    
    # 1. Clean up any invisible "Zombie" instances stuck in memory
    if hasattr(main, "_app_instance") and main._app_instance is not None:
        try:
            main._app_instance.window.close()
            main._app_instance.window.deleteLater()
        except: pass
        main._app_instance = None
        
    # 2. Build the new instance
    main._app_instance = main.PickerController()
    win = main._app_instance.window
    
    # 3. Force Parenting to Maya's Main Window (Prevents hiding behind Maya)
    try:
        from PySide2 import QtWidgets, QtCore
    except ImportError:
        from PySide6 import QtWidgets, QtCore
        
    maya_win = None
    for w in QtWidgets.QApplication.topLevelWidgets():
        if w.objectName() == "MayaWindow":
            maya_win = w
            break
            
    if maya_win:
        win.setParent(maya_win)
        win.setWindowFlags(QtCore.Qt.Window) # Keep it a floating window

    # 4. Show, Raise, and Activate
    win.show()
    win.raise_()
    win.activateWindow()