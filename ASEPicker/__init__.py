def launch():
    from . import main
    
    # Store the instance so Maya's garbage collector doesn't delete the UI
    main._app_instance = main.PickerController()
    
    # Use the public show() method so the controller controls its own display
    main._app_instance.show()