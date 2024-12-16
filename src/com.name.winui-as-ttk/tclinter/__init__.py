import os
import sys

from abc import ABC, abstractmethod
from enum import auto, Enum
from functools import singledispatch
from math import gcd
from string import ascii_lowercase as alphabet
from typing import (
    Tuple, Optional, Union,
    Iterable as IterableType)

_roots = list()


class InstantiatedError(RuntimeError):
    
    def __init__(self, varname):
        super().__init__(varname, "is already instantiated")


class HasTcl:

    @property
    def tk(self): return self.__tk

    @tk.setter
    def tk(self, val):
        if self.__tk is not None: raise InstantiatedError("\"global __tk\"")

        self.__tk = val
    
    @property
    def tcl_varname(self): return self.__tcl_varname

    @tcl_varname.setter
    def tcl_varname(self, val):
        if self.__tcl_varname is not None: raise InstantiatedError(self.__class__.__name__ + " __tcl_varname")

        self.__tcl_varname = val
    
    def do(self, *args):
        """Execute commands directly to the TCL Interpreter. See `Tkapp_Call` in "_tkinter.c\""""
        
        self.tk.call(*args)
    
    def splitlist(self, x):
        return self.tk.splitlist(x)
    
    def createcommand(self, name, func):
        self.tk.createcommand(name, func)
    
    def deletecommand(self, command):
        self.tk.deletecommand(command)
    
    def settrace(self, debugger):
        # See `_tkinter_tkapp_settrace` in "_tkinter.c"
        self.tk.settrace(debugger)


class Callable:
    
    def __init__(self, *args):
        self.functions = list(arg for arg in args if callable(arg))
    
    def __call__(self, *args):
        for function in reversed(self.functions):
            args = function(*args) if args is not None else function()
        
        return args


class TCL(Enum):
    """Enumeration of TCL CMD commands, which may be found in https://www.tcl.tk/man/tcl/TclCmd/contents.htm"""

    @staticmethod
    def _generate_next_value_(name, start, count, last_values): return name.lower()

    DESTROY                                                            = auto()


class HasTclCommands(HasTcl):

    __tcl_commands = None
    __tcl_flags = None

    @property
    def commands(self): return self.__tcl_commands

    @commands.setter
    def commands(self, val):
        if self.__tcl_commands is not None: raise InstantiatedError(self.__class__.__name__ + "__tcl_commands")

        self.__tcl_commands = val
    
    @singledispatch
    def addcommand(self, val):
        raise NotImplementedError("Unsupported type")
    
    @addcommand.register(Callable)
    def _(self, val):
        func = val.__call__
        name = repr(id(func))

        try:
            name += func.__func__.__name__
        except AttributeError: pass

        self.createcommand(name, func)
        self.commands.update({name: func})

        return name
    
    def addalias(self, alias, name):
        if name not in self.commands: raise RuntimeError()

        self.commands.update({alias: name})
    
    @property
    def flags(self): return self.__tcl_flags

    @flags.setter
    def flags(self, val):
        if self.__flags is not None: raise InstantiatedError(self.__class__.__name__ + "__tcl_flags")

        self.__tcl_flags = val
    
    @singledispatch
    def addflag(self, val, *args):
        raise NotImplementedError("Unsupported type")
    
    @addflag.register(str)
    def _(self, val, *args):
        self.flags[val] = ("-" + val,) + tuple(args)

        return val

    def __init__(self, **kw):
        self.commands = dict()
        self.flags = dict()

        for key, vaue in kw.items():
            if callable(value):
                value = Callable(value)
            elif any((
                    isinstance(value, list) and all(map(callable, value)),
                    isinstance(value, tuple) and all(map(callable, value)))):
                value = Callable(*value)
            
            if isinstance(value, Callable):
                command = self.addcommand(value)
                self.addalias(key, command)

                continue

            self.addflag(key, value)
    
    def __del__(self):
        for command in tuple(self.commands):
            self.commands.pop(command)
            self.deletecommand(command)

        self.do(TCL.DESTROY.value, self.tcl_varname)


class HasInstanceTracking:

    @classmethod
    def getinstances(cls): return cls.__instances

    @classmethod
    def addinstance(cls, instance):
        cls.__instances.add(instance)
    
    @classmethod
    def delinstance(cls, instance):
        cls.__instances.remove(instance)


class HasChildren:

    @property
    def children(self):
        return self.__children
    
    @children.setter
    def children(self, val):
        if self.__children is not None: raise InstantiatedError(self.__class__.__name__ + "__children")

        self.__children = val
    
    def __del__(self):
        for child in tuple(self.children):
            self.children.remove(child)

            del child


def get_runningfile(exempt: Optional[Union[IterableType[str], str]]=None) -> str:
    """Get the name of the running file, optionally excluding certain file extentions.

    Arguments:
        exempt: An optional string or iterable of strings representing file extensions to exclude
    
    Returns:
        The full filename if the extension is not excluded, otherwise the filename of the extension"""

    fullname = os.path.basename(sys.argv[0])
    filename, fileext = os.path.splitext(fullname)

    if any((
            exempt is None,
            isinstance(exempt, str) and fileext != exempt,
            isinstance(exempt, Iterable) and fileext not in exempt)):
        return fullname
    
    return filename

@singledispatch
def delroot(arg=None):
    if arg is None:
        return delroot.dispatch(type(None))()
    
    return delroot.dispatch(type(arg))(arg)

@delroot.register(type(None))
def _(arg=None):
    global _roots

    root = _roots.pop(0)

    del root

@delroot.register(int)
def _(index):
    global _roots

    root = _roots.pop(index)

    del root


class __Root(HasTclCommands, HasChildren):

    __children = None
    __tcl_varname = None
    __tk = None

    def __init__(self,
            basename: Optional[str]=None,
            classname: str="Root",
            init_tk: bool=True,
            screenname: Optional[str]=None,
            sync: bool=False,
            use: Optional[str]=None,
            debugger: Optional[object]=None):
        """Arguments:
            basename:   DEPRECATED. This is a needed field in the "_tkinter.c" file, but will not be used in any way
            classname:  The name of the class in the program code
            init_tk:    From "_tkinter.c": if `False`, then `Tk_Init()` does not get called
            screenname: An optional string representing the screen to display child widgets in
            sync:       From "_tkinter.c": if `True`, then pass `-sync` to wish
            use:        From "_tkinter.c": if not `None`, then pass `-use` to wish"""
        
        if basename is None:
            basename = get_runningfile(exempt={".py", ".pyc"})
        
        self.tk = _tkinter.create(  # See `_tkinter_create_impl` in "_tkinter.c"
            screenname, basename, classname,
            False,  # The `interactive` arg doesn't get used in this module, but is needed in the "_tkinter.c" file
            1,      # The `wantobjects` arg doesn't get used in this module, but is needed in the "_tkinter.c" file
            init_tk, sync, use)

        HasTclCommands.__init__(self)
        
        if debugger is not None:
            self.settrace(debugger)

        self.children = set()
    
    def __del__(self):
        HasTclCommands.__del__(self)
        HasChildren.__del__(self)

        delroot(self)


@delroot.register(__Root)
def delroot(root):
    global _roots

    index = _roots.index(root)
    root = _roots.pop(index)

    del root

@singledispatch
def getroot(index=None):
    if index is None:
        return getroot.dispatch(type(None))()
    
    return getroot.dispatch(type(index))(index)

@getroot.register(type(None))
def _(index=None):
    global _roots

    if not len(_roots):
        _roots.append(__Root())
    
    return _roots[0]

@getroot.register(int)
def _(index):
    global _roots

    return _roots[index]


class HasParent:

    @property
    def parent(self):
        return self.__parent
    
    @parent.setter
    def parent(self, val):
        if self.__parent is not None: raise InstantiatedError(self.__class__.__name__ + "__parent")

        self.__parent = val
    
    def __init__(self, parent=None):
        if parent is None:
            parent = getroot()
        
        if not isinstance(parent, HasChildren): raise RuntimeError()

        self.parent = parent
        self.parent.children.add(self)
    
    def __del__(self):
        self.parent.remove(self)


class BareWidget(HasTclCommands, HasInstanceTracking, HasParent, HasChildren):
    
    __instances = set()

    __children = None
    __parent = None
    __tcl_varname = None
    __tk = None

    def __init__(self, widgetname, parent=None, **kw):
        HasParent.__init__(self, parent)

        name = None

        if "name" in kw:
            name = kw["name"]

            del kw["name"]
        
        if not name:
            name = self.__class__.__name__.lower()
            index = len(self.__class__.getinstances())

            if index:
                name += str(index)
        
        if not isinstance(parent, HasTcl): raise RuntimeError()

        self.tk = self.parent.tk
        
        HasTclCommands.__init__(self, **kw)

        flags = list()

        for key, value in kw.items():
            if any((
                    callable(value),
                    isinstance(value, tuple) and all(map(callable, value)),
                    isinstance(value, list) and all(map(callable, value)))):
                continue

            flags.extend(self.flags[key])

        self.tcl_varname = self.parent.tcl_varname + "!" + name + "."
        self.widgetname = widgetname
        self.do = self.parent.do
        self.do((self.widgetname, self.tcl_varname) + tuple(flags))

        self.children = set()

        self.__class__.addinstance(self)
    
    def __del__(self):
        HasTclCommands.__del__(self)

        self.__class__.delinstance(self)

        HasParent.__del__(self)
        HasChildren.__del__(self)


class Observers(dict):
    
    def __setitem__(self, key, value):
        if not callable(value): raise ValueError()

        if not isinstance(key, str):
            key = str(key)
        
        super().__setitem__(key, value)
    
    def __getitem__(self, key):
        return super().__getitem__(key)
    
    def __call__(self, *args, **kw):
        result = dict()

        if not len(args) and not len(kw):
            for name, observer in self.items():
                result[name] = observer()

            return result
        
        for key in args:
            result[key] = self[key]()
        
        for key, value in kw.items():
            result[key] = self[key](value) if not isinstance(value, (tuple, list)) else self[key](*value)
        
        return result


class HasObserver:

    __observers = None

    @property
    def observers(self): return self.__observers

    @observers.setter
    def observers(self, val):
        if self.observers is not None: raise InstantiatedError(self.__class__.__name__ + " __observers")

        self.__observers = val
    
    def __init__(self):
        self.observers = Observers()


class Variable(HasObserver):

    __value = None

    @property
    def value(self): return self.__value

    @value.setter
    def value(self, val):
        self.__value = val

        self.observers()
    
    def __init__(self, default=None, value=None):
        HasObserver.__init__(self)
        
        if value is None:
            if not callable(default): raise ValueError()
            value = default()
        
        self.value = value


class Bounds:

    __minimum = None
    __maximum = None
    __enforces = None

    @property
    def minimum(self): return self.__minimum

    @property
    def maximum(self): return self.__maximum

    @property
    def enforces(self): return self.__enforces

    @minimum.setter
    def minimum(self, val):
        if not isinstance(val, type(self.enforces.value)): raise TypeError

        if self.maximum is not None and self.maximum < val: raise ValueError()

        self.__minimum = val
    
    @maximum.setter
    def maximum(self, val):
        if not isinstance(val, type(self.enforces.value)): raise TypeError
        
        if self.minimum is not None and val < self.minimum: raise ValueError()

        self.__maximum = val
    
    def enforce(self):
        if not (self.minimum <= self.enforces.value <= self.maximum): raise RuntimeError()
    
    def __init__(self, obj, minimum=None, maximum=None):
        if not isinstance(obj, Variable): raise RuntimeError()

        self.__enforces = obj
        self.enforces.observers[id(self)] = self.enforce

        if minimum is not None:
            self.minimum = minimum
        
        if maximum is not None:
            self.maximum = maximum


class Ratio:

    __numerator = None
    __denominator = None
    __reduced = None

    @property
    def numerator(self): return self.__numerator

    @property
    def denominator(self): return self.__denominator

    @property
    def reduced(self): return self.__reduced

    @numerator.setter
    def numerator(self, val):
        if val != self.numerator:
            self.__reduced = False

        self.__numerator = val

    @denominator.setter
    def denominator(self, val):
        if val != self.denominator:
            self.__reduced = False

        self.__denominator = val
    
    def reduce(self):
        cd = gcd(self.numerator, self.denominator)
        self.numerator //= cd
        self.denominator //= cd

        self.__reduced = True
    
    @property
    def ratio(self):
        if not self.reduced:
            self.reduce()
        
        return self.numerator, self.denominator
    
    def __init__(self, numerator=None, denominator=None):
        if numerator is None:
            numerator = 1
        
        self.numerator = numerator

        if denominator is None:
            denominator = 1
        
        self.denominator = denominator


class Window(BareWidget):

    def __init__(self):
        BareWidget.__init__(self)
    
    def __del__(self):
        BareWidget.__del__(self)


def test_bounds():
    number = Variable(value=5)
    bounds = Bounds(number, 0, 10)

    for n in range(20):
        try:
            number.value = n
            
            assert bounds.minimum <= n <= bounds.maximum
        except RuntimeError as e: assert not (bounds.minimum <= n <= bounds.maximum)

def test():
    try:
        test_bounds()

        return True
    except: return False

def main():
    print(f"tclinter: tests returned...", test())

if __name__ == "__main__":
    main()
