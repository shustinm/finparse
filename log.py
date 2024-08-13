import sys

from loguru import logger


def add_padding(record):
    """
    Logger filter function that adds padding to each record
    """
    # Calculate the lengths of the module and function sections for alignment
    module_length = 20 - len(record["name"])
    function_length = 20 - len(record["function"]) - len(str(record["line"]))
    record["extra"]["module_padding"] = " " * max(module_length, 0)
    record["extra"]["function_padding"] = " " * max(function_length, 0)
    return record


def configure_log(verbose: bool):
    logger.remove()  # Remove the default logger

    # Configure the logger with aligned format and default colors
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> │ "
        "<level>{level: <8}</level> │ "
        "<cyan>{name}</cyan>{extra[module_padding]} │ "
        "<cyan>{function}</cyan>:{line}{extra[function_padding]} │ "
        "<level>{message}</level>",
        filter=add_padding,
        level="DEBUG" if verbose else "INFO",
    )
