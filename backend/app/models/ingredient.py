from enum import Enum


class Unit(str, Enum):
    GRAM = "g"
    KILOGRAM = "kg"
    MILLILITER = "ml"
    CENTILITER = "cl"
    DECILITER = "dl"
    LITER = "L"
    PIECE = "piece"
    TABLESPOON = "tbsp"
    TEASPOON = "tsp"
    CUP = "cup"
    OUNCE = "oz"
    POUND = "lb"
    BUNCH = "bunch"
    PINCH = "pinch"
    CLOVE = "clove"
    SLICE = "slice"
    CAN = "can"
    PACKAGE = "package"
