import os

from exceptions import VCSException

class Environment:
    VARS = {
        'verbosity': {
            'var': 'VCS_VERBOSITY',
            'default': 0
        },

        'log.verbosity': {
            'var': 'VCS_LOG_VERBOSITY',
            'default': 0
        },

        'repo': {
            'var': 'VCS_REPO'
        },
        'manifest.root': {
            'var': 'VCS_MANIFEST'
        },
        'manifest.default_project_set': {
            'var': 'VCS_DEFAULT_PROJECT_SET',
            'default': None
        }
    }

    def __init__(self):
        self._config = {}
        for name, opts in Environment.VARS.items():
            try:
                self._config[name] = os.environ[opts['var']]
            except KeyError as e:
                if 'default' in opts:
                    self._config[name] = opts['default']
                else:
                    raise VCSException(
                        f"Required environment variable '{name}' not set"
                    ) from e

    def get(self, name: str):
        return self._config[name]
