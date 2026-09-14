from datetime import date, timedelta

from workalendar.america import Brazil


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
