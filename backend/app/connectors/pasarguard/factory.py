from .configurable import ConfigurablePasarGuard


def build_connector(config):
    return ConfigurablePasarGuard(**config)
