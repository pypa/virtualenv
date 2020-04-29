from virtualenv.activation import PythonActivator
from virtualenv.config.cli.parser import VirtualEnvOptions
from virtualenv.run import session_via_cli


def test_from_py3_to_py2(session_app_data, cross_python, special_name_dir):
    options = VirtualEnvOptions()
    cli_args = [
        str(special_name_dir),
        "-p",
        str(cross_python.executable),
        "--app-data",
        str(session_app_data.path),
        "--without-pip",
        "--activators",
        "",
    ]
    session = session_via_cli(cli_args, options)
    activator = PythonActivator(options)
    session.creator.bin_dir.mkdir(parents=True)
    result = activator.generate(session.creator)
    content = result.read_text()
    assert "\"'" not in content
