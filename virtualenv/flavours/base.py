import os


class BaseFlavour(object):
    def python_bins(self, version_info):
        return [
            "python{}".format(".".join(map(str, version_info[:i])))
            for i in range(3)
        ]
