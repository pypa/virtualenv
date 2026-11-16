Release the thread lock for each nested app-data lock acquisition, so waiting threads can acquire it after the outermost
context exits.
