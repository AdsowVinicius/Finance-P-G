from datetime import date, timedelta

from workalendar.america import Brazil

from app.models.enums import RegraDiaUtilCategoria


class DiaUtilCalculator:
    """Único lugar do sistema que decide o que é dia útil no Brasil.

    Sábado, domingo e feriados nacionais (via workalendar) empurram a data
    para o próximo dia útil. Não existe tabela de feriados no MVP — ver
    nota de design no schema.sql.
    """

    def __init__(self) -> None:
        self._calendario = Brazil()

    def proximo_dia_util(self, data: date) -> date:
        ajustada = data
        while not self._calendario.is_working_day(ajustada):
            ajustada += timedelta(days=1)
        return ajustada

    def eh_dia_util(self, data: date) -> bool:
        return self._calendario.is_working_day(data)

    def ajustar_por_categoria(self, data: date, regra: RegraDiaUtilCategoria) -> date:
        """Deslocamento alternativo, usado só quando o lançamento tem uma
        categoria vinculada — não mexe em proximo_dia_util(), que continua
        sendo o padrão pra lançamento sem categoria.

        - funcionario: sábado conta como dia útil (só domingo/feriado empurra,
          pro próximo dia útil real via workalendar — sábado nunca empurra).
        - bancaria: só segunda a sexta e nunca feriado nacional (banco não
          abre); cair num desses dias empurra pra trás, até o dia útil
          anterior (nunca pra frente).
        """
        if regra == RegraDiaUtilCategoria.funcionario:
            ajustada = data
            while ajustada.weekday() != 5 and not self._calendario.is_working_day(ajustada):
                ajustada += timedelta(days=1)
            return ajustada
        if regra == RegraDiaUtilCategoria.bancaria:
            ajustada = data
            while not self._calendario.is_working_day(ajustada):
                ajustada -= timedelta(days=1)
            return ajustada
        return data
