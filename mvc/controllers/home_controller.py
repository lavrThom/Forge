# pyright: strict
from core.http.request import Request
from core.http.response import Response
from core.mvc.controller.base_controller import BaseController


class HomeController(BaseController):

    @staticmethod
    def index(request: Request) -> Response:
        return BaseController.render("home/index.html", request=request)

    @staticmethod
    def charte(request: Request) -> Response:
        # Page de référence de la charte graphique (thème « Accessible chaleureux »).
        # Les tokens s'éditent dans static/src/input.css ; cette page montre le résultat.
        return BaseController.render("pages/charte.html", request=request)
