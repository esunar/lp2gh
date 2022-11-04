import re


invalid_re = re.compile(r'[^a-zA-Z0-9_ ,.\-]')


def create_label(labels, label, color=None):
    translated = translate_label(label)
    found_item = next(
        (lbl for lbl in labels.datalist if lbl['name'] == translated), None)
    if found_item is None:
        params = {'name': translated}
        if color:
            params['color'] = color
        return labels.append(**params)
    else:
        return found_item


def translate_label(label):
    """GitHub only allows certain characters in labels.

    Specifically, alphanum and _ ,.-

    """
    return invalid_re.sub('_', label)
