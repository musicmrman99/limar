import os

from exceptions import VCSException

class Config:
    REQUIRED_ENV_VARS = {
        'repo': 'VCS_REPO',
        'manifest': 'VCS_MANIFEST'
    }
    OPTIONAL_ENV_VARS = {
        'verbosity': {'var': 'VCS_VERBOSITY', 'default': 0},
        'log_verbosity': {'var': 'VCS_LOG_VERBOSITY', 'default': 0}
    }

    def __init__(self):
        self._config = {}

        for (key, value) in Config.REQUIRED_ENV_VARS.items():
            try:
                self._config.update({key: os.environ[value]})
            except KeyError as e:
                raise VCSException(
                    f"Required environment variable '{value}' not set"
                ) from e

        for (key, value) in Config.OPTIONAL_ENV_VARS.items():
            try:
                self._config.update({key: os.environ[value['var']]})
            except KeyError:
                pass

    def get(self, name: str):
        return self._config[name]

    def __getattr__(self, name: str):
        try:
            return self._config[name]
        except KeyError as e:
            raise AttributeError() from e
