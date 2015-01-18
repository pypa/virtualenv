#include "Python.h"

static PyObject *hello_world(PyObject *self, PyObject *args) {
    return Py_BuildValue("s", "hello, world!");
}

static PyMethodDef module_functions[]={
    {"hello_world", hello_world, METH_VARARGS, "Say hello."},
    {NULL}
};


#if PY_MAJOR_VERSION < 3
    PyMODINIT_FUNC inittest_cext(void) {
        Py_InitModule3("test_cext", module_functions, "Minimal test module.");
    }
#else
    static struct PyModuleDef moduledef = {
        PyModuleDef_HEAD_INIT,
        "test_cext",            /* m_name */
        "Minimal test module.", /* m_doc */
        -1,                     /* m_size */
        module_functions,       /* m_methods */
        NULL,                   /* m_reload */
        NULL,                   /* m_traverse */
        NULL,                   /* m_clear */
        NULL,                   /* m_free */
    };

    PyMODINIT_FUNC PyInit_test_cext(void) {
        return PyModule_Create(&moduledef);
    }
#endif
