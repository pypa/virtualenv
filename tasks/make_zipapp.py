"""https://docs.python.org/3/library/zipapp.html"""
import argparse
import io
import os.path
import zipapp
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--dest")
    args = parser.parse_args()

    if args.dest is not None:
        dest = args.dest
    else:
        dest = os.path.join(args.root, "virtualenv.pyz")

    filenames = {"LICENSE.txt": "LICENSE.txt", os.path.join("src", "virtualenv.py"): "virtualenv.py"}
    for support in os.listdir(os.path.join(args.root, "src", "virtualenv_support")):
        support_file = os.path.join("virtualenv_support", support)
        filenames[os.path.join("src", support_file)] = support_file

    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as zip_file:
        for filename in filenames:
            zip_file.write(os.path.join(args.root, filename), filename)

        zip_file.writestr("__main__.py", "import virtualenv; virtualenv.main()")

    bio.seek(0)
    zipapp.create_archive(bio, dest)
    print("zipapp created at {}".format(dest))


if __name__ == "__main__":
    exit(main())
