from abc import ABCMeta, abstractmethod, abstractproperty



class Config(object, metaclass=ABCMeta):
    @abstractmethod
    def to_dict(self):
        pass

    @classmethod
    def from_dict(cls, obj_dict):
        raise NotImplementedError


class ProcessingUnitConfig(Config, metaclass=ABCMeta):
    """Represents the configuration object needed to initialize a
        :class:`.ProcessingUnit`"""

    @abstractproperty
    def unit_name(self):
        raise NotImplementedError

    def set_unit_name(self, value):
        pass

    def get_required_resources(self):
        return None


class DefaultProcessingUnitConfig(dict, ProcessingUnitConfig):
    """Default config implemented as a simple dict"""

    @property
    def unit_name(self):
        return self["unit_name"]

    def set_unit_name(self, value):
        self["unit_name"] = value

    def to_dict(self):
        return self

    @classmethod
    def from_dict(cls, obj_dict):
        return cls(obj_dict)
