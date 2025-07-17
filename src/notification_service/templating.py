import jinja2

from pathlib import Path
from .exceptions import TemplateRenderingError

class TemplateManager:
    def __init__(self):
        templates_dir = Path(__file__).parent / "templates"
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(templates_dir),
            autoescape=jinja2.select_autoescape(['html', 'xml'])
        )
        print(f"TemplateManager inicializado. Lendo templates de: {templates_dir}")

    def render(self, template_name: str, context: dict) -> str:
        """
        Renders a Jinja2 template with the given context.
        Raises TemplateRenderingError if the template is not found or fails to render.
        """
        try:
            template = self.env.get_template(template_name)
            return template.render(context)
        except jinja2.exceptions.TemplateNotFound as e:
            print(f"[TEMPLATE_ERROR] Template não encontrado: {template_name}")
            raise TemplateRenderingError(f"Template não encontrado: {template_name}") from e
        except jinja2.exceptions.TemplateError as e:
            print(f"[TEMPLATE_ERROR] Erro ao renderizar o template {template_name}: {e}")
            raise TemplateRenderingError(f"Erro de renderização no template {template_name}") from e