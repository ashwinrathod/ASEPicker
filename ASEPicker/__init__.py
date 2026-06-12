def launch():
    from . import main
    
    # 1. Check if the tool is already running in the background
    if hasattr(main, "_app_instance") and main._app_instance is not None:
        try:
            main._app_instance.window.show()
            main._app_instance.window.raise_()
            main._app_instance.window.activateWindow()
            return
        except Exception:
            pass # C++ object was deleted, proceed to rebuild
            
    # 2. Store the instance so Maya's garbage collector doesn't delete the UI
    main._app_instance = main.PickerController()
    
    # 3. Show and force it to the front
    main._app_instance.window.show()
    main._app_instance.window.raise_()
    main._app_instance.window.activateWindow()