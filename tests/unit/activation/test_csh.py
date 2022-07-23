from virtualenv.activation import CShellActivator


def test_csh(activation_tester_class, activation_tester):
    class Csh(activation_tester_class):
        def __init__(self, session):
            super().__init__(CShellActivator, session, "csh", "activate.csh", "csh")

        def print_prompt(self):
            return "echo 'source \"$VIRTUAL_ENV/bin/activate.csh\"; echo $prompt' | csh -i"

    activation_tester(Csh)
