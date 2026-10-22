/*
 * Minimal CPython launcher for the Python 3.14 runtime that ships inside
 * Fusion 360's bundle.  Fusion's own `bin/python3` is a stub that points at
 * a Python.app which is missing from the installed bundle, so we link
 * directly against Python.framework instead.
 *
 * Usage:  ./fpy <script.py> [args...]
 */
#include <Python.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: %s <script.py> [args...]\n", argv[0]);
        return 2;
    }

    PyStatus status;
    PyConfig config;

    PyConfig_InitPythonConfig(&config);
    config.install_signal_handlers = 0;

    /* Keep argv[0] as the program name so the interpreter can handle
     * options such as -c / -m / script.py normally. */
    char **args = (char **)malloc(sizeof(char *) * (size_t)argc);
    if (!args) {
        fprintf(stderr, "fpy: out of memory\n");
        return 1;
    }
    args[0] = argv[0];
    for (int i = 1; i < argc; i++) {
        args[i] = argv[i];
    }

    status = PyConfig_SetBytesArgv(&config, argc, args);
    free(args);
    if (PyStatus_Exception(status)) {
        PyConfig_Clear(&config);
        fprintf(stderr, "fpy: failed to set argv\n");
        return 1;
    }

    status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) {
        fprintf(stderr, "fpy: failed to initialize Python\n");
        return 1;
    }

    int rc = Py_RunMain();

    if (Py_FinalizeEx() < 0) {
        return 1;
    }
    return rc;
}
