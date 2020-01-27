#include <stdio.h>
#include <Python.h>

static PyObject * greet(PyObject * self, PyObject * args) {
  const char * name;
  if (!PyArg_ParseTuple(args, "s", & name)) {
    return NULL;
  }
  printf("Hello %s!\n", name);
  Py_RETURN_NONE;
}

static PyMethodDef GreetMethods[] = {
  {
    "greet",
    greet,
    METH_VARARGS,
    "Greet an entity."
  },
  {
    NULL,
    NULL,
    0,
    NULL
  }
};

static struct PyModuleDef greet_definition = {
  PyModuleDef_HEAD_INIT,
  "greet",
  "A Python module that prints 'greet world' from C code.",
  -1,
  GreetMethods
};

PyMODINIT_FUNC PyInit_greet(void) {
  return PyModule_Create( & greet_definition);
}
