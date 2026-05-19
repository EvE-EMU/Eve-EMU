from django.template import (Context, Template, Node, TemplateSyntaxError, Variable, Library)

register = Library()

TEMPLATE = """
<img src="https://images.evetech.net/characters/{{ id }}/portrait?size={{ size }}">
"""


@register.tag(name='character_portrait')
def do_character_portrait(parser, token):
    try:
        # if not passed, append default portrait size
        if len(token.split_contents()) < 3:
            token.contents += ' 32'
        tag_name, _id, _size = token.split_contents()
    except ValueError:
        raise TemplateSyntaxError("%r tag requires 1 argument" % token.contents.split()[0])
    return CharacterPortraitNode(_id, _size)


class CharacterPortraitNode(Node):
    def __init__(self, _id, _size):
        self.id = Variable(_id)
        self.size = Variable(_size)

    def render(self, context):
        _values = {
            'id':  self.id.resolve(context),
            'size': self.size.resolve(context)
        }

        t = Template(TEMPLATE)
        c = Context(_values)
        return t.render(c)


# register = Library()
# register.tag('character_portrait', do_character_portrait)
