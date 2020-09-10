import six

if six.PY3:
    import winreg
else:
    # noinspection PyUnresolvedReferences
    import _winreg as winreg

hive_open = {
    (winreg.HKEY_CURRENT_USER, "Software\\Python", 0, winreg.KEY_READ): 78701856,
    (winreg.HKEY_LOCAL_MACHINE, "Software\\Python", 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY): 78701840,
    (winreg.HKEY_LOCAL_MACHINE, "Software\\Python", 0, winreg.KEY_READ | winreg.KEY_WOW64_32KEY): OSError(
        2,
        "The system cannot find the file specified",
    ),
}
key_open = {
    78701152: {
        "Anaconda37-32\\InstallPath": 78703200,
        "Anaconda37-32": 78703568,
        "Anaconda37-64\\InstallPath": 78703520,
        "Anaconda37-64": 78702368,
    },
    78701856: {"ContinuumAnalytics": 78701152, "PythonCore": 78702656},
    78702656: {
        "3.1\\InstallPath": 78701824,
        "3.1": 78700704,
        "3.2\\InstallPath": 78704048,
        "3.2": 78704368,
        "3.3\\InstallPath": 78701936,
        "3.3": 78703024,
        "3.5\\InstallPath": 78703792,
        "3.5": 78701792,
        "3.6\\InstallPath": 78701888,
        "3.6": 78703424,
        "3.7-32\\InstallPath": 78703600,
        "3.7-32": 78704512,
        "3.8\\InstallPath": OSError(2, "The system cannot find the file specified"),
        "3.8": 78700656,
        "3.9\\InstallPath": 78703632,
        "3.9": 78702608,
        "3.X": 78703088,
    },
    78702960: {"2.7\\InstallPath": 78700912, "2.7": 78703136, "3.4\\InstallPath": 78703648, "3.4": 78704032},
    78701840: {"PythonCore": 78702960},
}
value_collect = {
    78703568: {"SysVersion": ("3.7", 1), "SysArchitecture": ("32bit", 1)},
    78703200: {
        "ExecutablePath": ("C:\\Users\\user\\Miniconda3\\python.exe", 1),
        "ExecutableArguments": OSError(2, "The system cannot find the file specified"),
    },
    78702368: {"SysVersion": ("3.7", 1), "SysArchitecture": ("64bit", 1)},
    78703520: {
        "ExecutablePath": ("C:\\Users\\user\\Miniconda3-64\\python.exe", 1),
        "ExecutableArguments": OSError(2, "The system cannot find the file specified"),
    },
    78700704: {"SysVersion": ("3.6", 1), "SysArchitecture": ("magic", 1)},
    78701824: {
        "ExecutablePath": ("C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe", 1),
        "ExecutableArguments": OSError(2, "The system cannot find the file specified"),
    },
    78704368: {"SysVersion": ("3.6", 1), "SysArchitecture": (100, 4)},
    78704048: {
        "ExecutablePath": ("C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe", 1),
        "ExecutableArguments": OSError(2, "The system cannot find the file specified"),
    },
    78703024: {"SysVersion": ("3.6", 1), "SysArchitecture": ("64bit", 1)},
    78701936: {
        "ExecutablePath": OSError(2, "The system cannot find the file specified"),
        None: OSError(2, "The system cannot find the file specified"),
    },
    78701792: {
        "SysVersion": OSError(2, "The system cannot find the file specified"),
        "SysArchitecture": OSError(2, "The system cannot find the file specified"),
    },
    78703792: {
        "ExecutablePath": ("C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python35\\python.exe", 1),
        "ExecutableArguments": OSError(2, "The system cannot find the file specified"),
    },
    78703424: {"SysVersion": ("3.6", 1), "SysArchitecture": ("64bit", 1)},
    78701888: {
        "ExecutablePath": ("C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe", 1),
        "ExecutableArguments": OSError(2, "The system cannot find the file specified"),
    },
    78704512: {"SysVersion": ("3.7", 1), "SysArchitecture": ("32bit", 1)},
    78703600: {
        "ExecutablePath": ("C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python37-32\\python.exe", 1),
        "ExecutableArguments": OSError(2, "The system cannot find the file specified"),
    },
    78700656: {
        "SysVersion": OSError(2, "The system cannot find the file specified"),
        "SysArchitecture": OSError(2, "The system cannot find the file specified"),
    },
    78702608: {"SysVersion": ("magic", 1), "SysArchitecture": ("64bit", 1)},
    78703632: {
        "ExecutablePath": ("C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python36\\python.exe", 1),
        "ExecutableArguments": OSError(2, "The system cannot find the file specified"),
    },
    78703088: {"SysVersion": (2778, 11)},
    78703136: {
        "SysVersion": OSError(2, "The system cannot find the file specified"),
        "SysArchitecture": OSError(2, "The system cannot find the file specified"),
    },
    78700912: {
        "ExecutablePath": OSError(2, "The system cannot find the file specified"),
        None: ("C:\\Python27\\", 1),
        "ExecutableArguments": OSError(2, "The system cannot find the file specified"),
    },
    78704032: {
        "SysVersion": OSError(2, "The system cannot find the file specified"),
        "SysArchitecture": OSError(2, "The system cannot find the file specified"),
    },
    78703648: {
        "ExecutablePath": OSError(2, "The system cannot find the file specified"),
        None: ("C:\\Python34\\", 1),
        "ExecutableArguments": OSError(2, "The system cannot find the file specified"),
    },
}
enum_collect = {
    78701856: ["ContinuumAnalytics", "PythonCore", OSError(22, "No more data is available", None, 259, None)],
    78701152: ["Anaconda37-32", "Anaconda37-64", OSError(22, "No more data is available", None, 259, None)],
    78702656: [
        "3.1",
        "3.2",
        "3.3",
        "3.5",
        "3.6",
        "3.7-32",
        "3.8",
        "3.9",
        "3.X",
        OSError(22, "No more data is available", None, 259, None),
    ],
    78701840: ["PyLauncher", "PythonCore", OSError(22, "No more data is available", None, 259, None)],
    78702960: ["2.7", "3.4", OSError(22, "No more data is available", None, 259, None)],
}
