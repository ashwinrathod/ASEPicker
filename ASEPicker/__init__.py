# ASEPicker/__init__.py

def launch():
    from . import main
    
    # Store the instance so Maya's garbage collector doesn't delete the UI
    main._app_instance = main.PickerController()