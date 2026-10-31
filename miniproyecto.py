"""Miniproyecto 1: la serie del grupo, de las líneas base al mejor modelo clásico.

Se corre de principio a fin con

    python miniproyecto.py

y deja las figuras en figuras/ y las tablas en resultados/ (la principal es
resultados/metricas.csv). El informe, docs/informe.md, cita las cifras y las
figuras que produce este guion.

Serie del grupo: uso mensual de tarjetas débito en el comercio minorista de
Islandia, enero de 2000 a agosto de 2013 (164 meses). Ficha en datos/README.md.
"""
import itertools
import warnings

import matplotlib

matplotlib.use("Agg")
import holidays  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf  # noqa: E402
from statsmodels.stats.diagnostic import acorr_ljungbox  # noqa: E402
from statsmodels.tsa.seasonal import STL  # noqa: E402
from statsmodels.tsa.statespace.sarimax import SARIMAX  # noqa: E402
from statsmodels.tsa.stattools import acf, adfuller, pacf  # noqa: E402

from comun import (RAIZ, backtest, cargar_serie, estacional_ingenuo,  # noqa: E402
                   fechas_siguientes, ingenuo)

warnings.filterwarnings("ignore")
FIGURAS = RAIZ / "figuras"
RESULTADOS = RAIZ / "resultados"
FIGURAS.mkdir(exist_ok=True)
RESULTADOS.mkdir(exist_ok=True)

MESES = ["ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sep", "oct", "nov", "dic"]


def titulo(texto):
    print("\n" + "=" * 70 + f"\n{texto}\n" + "=" * 70)


# ============================================================
# 1. La serie
# ============================================================
ARCHIVO = "datos/debito_islandia.csv"
FECHA = "fecha"
VALOR = "uso_debito"
PERIODO = 12

# Umbral para marcar un mes como atípico: residuo de la STL robusta mayor
# que UMBRAL veces la desviación robusta (1.4826 * MAD) de los residuos.
UMBRAL = 3.0

# Lo que se hizo con los huecos y con los datos atípicos, en una línea. Va
# a la columna `decision` de la tabla de métricas.
DECISION = ("Huecos: interpolación lineal (la serie no trae ninguno); "
            "atípicos (residuo STL > 3 MAD) se conservan por ser reales")


def detectar_atipicos(serie):
    """Meses cuyo residuo de la STL robusta supera UMBRAL desviaciones robustas."""
    residuo = STL(serie, period=PERIODO, robust=True).fit().resid
    escala = 1.4826 * np.median(np.abs(residuo - np.median(residuo)))
    z = (residuo - np.median(residuo)) / escala
    return pd.DataFrame({"valor": serie[np.abs(z) > UMBRAL],
                         "residuo": residuo[np.abs(z) > UMBRAL],
                         "z": z[np.abs(z) > UMBRAL]})


def preparar(serie):
    """Aplica la decisión del grupo sobre huecos y datos atípicos.

    - Huecos: si un mes viene vacío (NaN) se rellena por interpolación lineal
      en el tiempo entre sus vecinos. La serie de Islandia no trae ninguno,
      pero la regla queda en el código por si la fuente cambia.
    - Atípicos: se detectan con el residuo de una STL robusta y se imprimen,
      pero NO se modifican: son meses reales (no errores de captura) y el
      backtest debe medir los modelos sobre los datos tal como ocurrieron.
    Devuelve una serie sin NaN.
    """
    vacios = serie.isna().sum()
    serie = serie.interpolate(method="time").bfill().ffill()
    print(f"Huecos interpolados: {vacios}")

    atipicos = detectar_atipicos(serie)
    print(f"Atípicos (|z| > {UMBRAL} sobre el residuo STL robusto): "
          f"{len(atipicos)}")
    if len(atipicos):
        tabla = atipicos.copy()
        tabla.index = tabla.index.strftime("%Y-%m")
        print(tabla.round(3).to_string())
    atipicos.to_csv(RESULTADOS / "atipicos.csv", index_label="fecha")
    return serie


def graficar_serie(serie):
    atipicos = detectar_atipicos(serie)
    figura, eje = plt.subplots(figsize=(9, 3.4))
    eje.plot(serie.index, serie.to_numpy(), label="uso de tarjetas débito")
    eje.scatter(atipicos.index, atipicos["valor"], color="red", zorder=3,
                label=f"atípicos (|z| > {UMBRAL:g})")
    eje.axvspan(pd.Timestamp("2008-10-01"), pd.Timestamp("2009-12-01"),
                color="grey", alpha=0.15, label="crisis bancaria 2008-2009")
    eje.set_title("Uso mensual de tarjetas débito en Islandia (millones de ISK)")
    eje.set_ylabel(VALOR)
    eje.legend(loc="upper left", fontsize=8)
    figura.tight_layout()
    figura.savefig(FIGURAS / "serie.png", dpi=120)
    plt.close(figura)


# ============================================================
# 2. Descomposición
# ============================================================

def descomponer(serie):
    """STL robusta con periodo 12; guarda figuras/stl.png e imprime su lectura."""
    titulo("PARTE 2. Descomposición STL robusta (periodo 12)")
    stl = STL(serie, period=PERIODO, robust=True).fit()

    figura = stl.plot()
    figura.set_size_inches(9, 7)
    figura.suptitle("STL robusta, periodo 12", y=1.0)
    figura.tight_layout()
    figura.savefig(FIGURAS / "stl.png", dpi=120)
    plt.close(figura)

    tendencia = stl.trend
    print(f"Tendencia: {tendencia.iloc[0]:.2f} en {tendencia.index[0]:%Y-%m}, "
          f"{tendencia.iloc[-1]:.2f} en {tendencia.index[-1]:%Y-%m} "
          f"(crece {tendencia.iloc[-1] / tendencia.iloc[0]:.2f} veces)")
    anual = tendencia.groupby(tendencia.index.year).mean()
    print("Tendencia promedio por año:")
    print(" ".join(f"{a}:{v:.2f}" for a, v in anual.items()))
    crecimiento = 100 * anual.pct_change()
    print("Crecimiento anual de la tendencia (%):")
    print(" ".join(f"{a}:{v:.1f}" for a, v in crecimiento.dropna().items()))
    for desde, hasta in [(2000, 2007), (2007, 2010), (2010, 2013)]:
        tasa = 100 * ((anual[hasta] / anual[desde]) ** (1 / (hasta - desde)) - 1)
        print(f"  {desde}-{hasta}: {tasa:.1f} % anual compuesto")

    estacional = stl.seasonal.groupby(stl.seasonal.index.month).mean()
    estacional.index = MESES
    print("Componente estacional promedio por mes:")
    print(estacional.round(3).to_string())
    print(f"Mes más alto: {estacional.idxmax()} ({estacional.max():+.2f}); "
          f"más bajo: {estacional.idxmin()} ({estacional.min():+.2f})")
    print(f"Amplitud estacional al inicio (2000) y al final (2012): "
          f"{np.ptp(stl.seasonal['2000']):.2f} y {np.ptp(stl.seasonal['2012']):.2f}")

    residuo = stl.resid
    print(f"Residuo más grande: {residuo.abs().idxmax():%Y-%m} "
          f"({residuo[residuo.abs().idxmax()]:+.2f}); desviación estándar "
          f"del residuo: {residuo.std():.3f}")
    fuerza_est = max(0, 1 - residuo.var() / (stl.seasonal + residuo).var())
    fuerza_ten = max(0, 1 - residuo.var() / (tendencia + residuo).var())
    print(f"Fuerza de la tendencia: {fuerza_ten:.3f}; "
          f"fuerza de la estacionalidad: {fuerza_est:.3f}")
    return stl


# ============================================================
# 3. Estacionariedad e identificación
# ============================================================

def diferenciar(serie, d, D):
    for _ in range(D):
        serie = serie.diff(PERIODO)
    for _ in range(d):
        serie = serie.diff()
    return serie.dropna()


def estacionariedad(serie):
    """ADF sobre la serie, su diferencia regular, la estacional y las dos.

    Para cada versión se corren las tres especificaciones de la prueba
    (`n`: sin constante, `c`: constante, `ct`: constante y tendencia) y se
    marca la que corresponde a lo que se ve en la versión:
    - serie original: tiene tendencia, se usa `ct`;
    - diferencia regular o estacional: la tendencia se va, pero puede quedar
      un nivel distinto de cero, se usa `c`;
    - las dos diferencias: queda alrededor de cero, se usa `n`.
    Elige d y D, guarda la ACF y la PACF de la serie elegida y devuelve (d, D).
    """
    titulo("PARTE 3. Estacionariedad (ADF) e identificación")
    versiones = {"original (d=0, D=0)": ((0, 0), "ct"),
                 "regular (d=1, D=0)": ((1, 0), "c"),
                 "estacional (d=0, D=1)": ((0, 1), "c"),
                 "las dos (d=1, D=1)": ((1, 1), "n")}
    filas = []
    for nombre, ((d, D), elegida) in versiones.items():
        x = diferenciar(serie, d, D)
        fila = {"version": nombre, "d": d, "D": D, "n_obs": len(x),
                "regression": elegida}
        for reg in ["n", "c", "ct"]:
            fila[f"p_{reg}"] = adfuller(x, regression=reg, autolag="AIC")[1]
        fila["p_elegida"] = fila[f"p_{elegida}"]
        fila["estacionaria"] = fila["p_elegida"] < 0.05
        filas.append(fila)
    adf = pd.DataFrame(filas)
    adf.to_csv(RESULTADOS / "adf.csv", index=False)
    print("Valor p de la prueba ADF (H0: raíz unitaria) por versión y "
          "especificación:")
    print(adf.round(4).to_string(index=False))

    # Regla: la estacionalidad es visible, así que se toma D = 1 (la
    # diferencia estacional quita el patrón que se repite cada 12 meses).
    # Luego d = 0 si con solo D = 1 la ADF ya rechaza la raíz unitaria; si
    # no, d = 1.
    # La ADF solo mira la raíz unitaria regular. Para ver si queda una raíz
    # estacional se mira la ACF de la serie con solo d = 1 en 12, 24 y 36:
    # si decae muy despacio, la estacionalidad no se ha ido.
    solo_regular = acf(diferenciar(serie, 1, 0), nlags=36)
    print("\nACF de la serie con solo d=1 en los rezagos 12, 24 y 36: "
          + ", ".join(f"{solo_regular[k]:.3f}" for k in (12, 24, 36)))
    D = 1
    p_solo_estacional = adf.loc[2, "p_elegida"]
    d = 0 if p_solo_estacional < 0.05 else 1
    print(f"\nCon D=1 y d=0 el valor p (regression='c') es "
          f"{p_solo_estacional:.4f}"
          + (" < 0.05: basta la diferencia estacional." if d == 0 else
             " >= 0.05: hace falta además la diferencia regular."))
    print(f"Con d=1 y D=1 el valor p (regression='n') es "
          f"{adf.loc[3, 'p_elegida']:.4f}")
    print(f"Elegidos: d = {d}, D = {D}")

    x = diferenciar(serie, d, D)
    rezagos = 36
    figura, ejes = plt.subplots(2, 1, figsize=(9, 6))
    plot_acf(x, lags=rezagos, ax=ejes[0],
             title=f"ACF de la serie con d={d}, D={D}")
    plot_pacf(x, lags=rezagos, ax=ejes[1], method="ywm",
              title=f"PACF de la serie con d={d}, D={D}")
    for eje in ejes:
        for k in (12, 24, 36):
            eje.axvline(k, color="grey", lw=0.6, ls=":")
    figura.tight_layout()
    figura.savefig(FIGURAS / "acf_pacf.png", dpi=120)
    plt.close(figura)

    banda = 1.96 / np.sqrt(len(x))
    valores_acf = acf(x, nlags=rezagos)[1:]
    valores_pacf = pacf(x, nlags=rezagos, method="ywm")[1:]
    fuera_acf = [(k + 1, round(float(v), 3)) for k, v in enumerate(valores_acf)
                 if abs(v) > banda]
    fuera_pacf = [(k + 1, round(float(v), 3))
                  for k, v in enumerate(valores_pacf) if abs(v) > banda]
    print(f"Banda aproximada de 95 %: ±{banda:.3f} (n = {len(x)})")
    print("Rezagos de la ACF fuera de la banda (rezago, valor):", fuera_acf)
    print("Rezagos de la PACF fuera de la banda (rezago, valor):", fuera_pacf)
    return d, D


# ============================================================
# 4. Modelos clásicos
# ============================================================
# Cada modelo es una función modelo(entrenamiento, h) que devuelve h
# pronósticos y solo usa `entrenamiento`. Así entra al backtest común.

def ajustar(y, orden, orden_estacional, exog=None):
    return SARIMAX(y, exog=exog, order=orden, seasonal_order=orden_estacional,
                   ).fit(disp=False)


def elegir_sarima(serie, d, D):
    """Rejilla pequeña de órdenes (p, q, P, Q) comparada por AIC.

    Se ajusta con toda la serie preparada. Se elige el de menor AIC; si hay
    modelos a menos de 2 puntos de AIC del mejor (diferencia que no es
    significativa), se queda el de menor BIC entre ellos, que castiga más los
    parámetros (parsimonia). Revisa los residuos del elegido con Ljung-Box y
    guarda figuras/residuos.png. Devuelve el orden y el orden estacional.
    """
    titulo("PARTE 4. Rejilla SARIMA por AIC")
    filas = []
    for p, q, P, Q in itertools.product(range(3), range(3), range(2), range(2)):
        try:
            ajuste = ajustar(serie, (p, d, q), (P, D, Q, PERIODO))
            filas.append({"p": p, "q": q, "P": P, "Q": Q,
                          "parametros": p + q + P + Q,
                          "AIC": ajuste.aic, "BIC": ajuste.bic})
        except Exception as error:  # un orden que no converge no detiene todo
            print(f"  ({p},{d},{q})({P},{D},{Q}) no se pudo ajustar: {error}")
    rejilla = pd.DataFrame(filas).sort_values("AIC").reset_index(drop=True)
    rejilla["dAIC"] = rejilla["AIC"] - rejilla["AIC"].min()
    rejilla.to_csv(RESULTADOS / "rejilla_aic.csv", index=False)
    print(f"{len(rejilla)} modelos ajustados con d={d}, D={D}. "
          "Los 10 de menor AIC:")
    print(rejilla.head(10).round(2).to_string(index=False))

    cercanos = rejilla[rejilla["dAIC"] < 2]
    elegido = cercanos.sort_values(["BIC", "parametros"]).iloc[0]
    p, q, P, Q = (int(elegido[c]) for c in ("p", "q", "P", "Q"))
    orden, estacional = (p, d, q), (P, D, Q, PERIODO)
    print(f"\nModelos a menos de 2 de AIC del mejor: {len(cercanos)}. "
          f"Elegido (menor BIC entre ellos): SARIMA{orden}{estacional} "
          f"con AIC = {elegido['AIC']:.2f} y BIC = {elegido['BIC']:.2f}")

    ajuste = ajustar(serie, orden, estacional)
    print("\nCoeficientes del modelo elegido:")
    resumen = pd.DataFrame({"coef": ajuste.params, "error_est": ajuste.bse,
                            "p_valor": ajuste.pvalues})
    print(resumen.round(4).to_string())

    # Los primeros d + D*12 residuos son de arranque del filtro: se descartan.
    residuos = ajuste.resid.iloc[d + D * PERIODO:]
    gl = p + q + P + Q
    lb = acorr_ljungbox(residuos, lags=[12, 24], model_df=gl)
    lb.index.name = "rezago"
    lb.to_csv(RESULTADOS / "ljung_box.csv")
    print(f"\nLjung-Box sobre los residuos (grados de libertad descontados: "
          f"{gl}):")
    print(lb.round(4).to_string())
    print("Los residuos se comportan como ruido blanco (p > 0.05)"
          if (lb["lb_pvalue"] > 0.05).all() else
          "Queda autocorrelación en los residuos (p <= 0.05 en algún rezago)")
    print(f"Media de los residuos: {residuos.mean():.4f}; "
          f"desviación estándar: {residuos.std():.4f}")

    figura, ejes = plt.subplots(2, 2, figsize=(10, 6))
    ejes[0, 0].plot(residuos.index, residuos.to_numpy())
    ejes[0, 0].axhline(0, color="black", lw=0.7)
    ejes[0, 0].set_title("Residuos en el tiempo")
    ejes[0, 1].hist(residuos, bins=25, edgecolor="white")
    ejes[0, 1].set_title("Histograma de los residuos")
    plot_acf(residuos, lags=36, ax=ejes[1, 0], title="ACF de los residuos")
    plot_pacf(residuos, lags=36, ax=ejes[1, 1], method="ywm",
              title="PACF de los residuos")
    figura.suptitle(f"Diagnóstico de SARIMA{orden}{estacional}")
    figura.tight_layout()
    figura.savefig(FIGURAS / "residuos.png", dpi=120)
    plt.close(figura)

    experimento_log(serie, orden, estacional)
    return orden, estacional


def experimento_log(serie, orden, estacional):
    """Experimento: el mismo SARIMA sobre el logaritmo de la serie.

    La amplitud estacional crece con el nivel (estacionalidad multiplicativa),
    y eso puede dejar autocorrelación y varianza no constante en los
    residuos del modelo en niveles. El logaritmo convierte ese patrón en
    aditivo. Solo se imprime para comparar; no entra a la tabla.
    """
    print("\nExperimento: el mismo orden sobre log(serie)")
    ajuste = ajustar(np.log(serie), orden, estacional)
    residuos = ajuste.resid.iloc[orden[1] + estacional[1] * PERIODO:]
    gl = orden[0] + orden[2] + estacional[0] + estacional[2]
    lb = acorr_ljungbox(residuos, lags=[12, 24], model_df=gl)
    print("Ljung-Box de los residuos en logaritmo:")
    print(lb.round(4).to_string())

    def modelo_log(entrenamiento, h):
        ajuste = ajustar(np.log(entrenamiento), orden, estacional)
        return np.exp(ajuste.forecast(h).to_numpy())
    _, promedio = backtest(serie, modelo_log)
    print("Backtest del SARIMA en logaritmo (pronóstico devuelto con exp): "
          f"RMSE {promedio['RMSE']:.2f}, MAE {promedio['MAE']:.2f}, "
          f"MAPE {promedio['MAPE']:.2f}")


def modelo_sarima(orden, orden_estacional):
    """La función modelo(entrenamiento, h) del SARIMA elegido.

    En cada origen del backtest se vuelve a estimar con los datos hasta el
    origen, de modo que ningún dato posterior entra al ajuste.
    """
    def modelo(entrenamiento, h):
        ajuste = ajustar(entrenamiento, orden, orden_estacional)
        return ajuste.forecast(h).to_numpy()
    return modelo


def exogenas(serie):
    """Días hábiles de cada mes en Islandia, conocidos de antemano.

    Días hábiles = días de lunes a viernes que no son festivo oficial en
    Islandia (librería `holidays`, que incluye la Semana Santa, que cae en
    marzo o en abril según el año). Depende solo del calendario, así que se
    conoce con años de anticipación: no hay fuga de información. Cubre la
    serie y los 12 meses siguientes. Se centra restando 21 para que el
    coeficiente se lea como el efecto de un día hábil más que lo normal.
    """
    fechas = pd.date_range(serie.index[0], periods=len(serie) + 12, freq="MS")
    festivos = holidays.country_holidays(
        "IS", years=range(fechas[0].year, fechas[-1].year + 1))
    dias = []
    for inicio in fechas:
        mes = pd.date_range(inicio, inicio + pd.offsets.MonthEnd(0), freq="D")
        habiles = [f for f in mes if f.dayofweek < 5 and f.date() not in festivos]
        dias.append(len(habiles))
    x = pd.DataFrame({"dias_habiles": np.array(dias) - 21}, index=fechas)
    x.index.freq = "MS"
    return x


def modelo_sarimax(orden, orden_estacional, x):
    """modelo(entrenamiento, h) de un SARIMAX con exógenas x.

    Ajusta con x.loc[entrenamiento.index] y pronostica con
    x.loc[fechas_siguientes(entrenamiento, h)]: los días hábiles futuros salen
    del calendario, no de los datos posteriores al origen.
    """
    def modelo(entrenamiento, h):
        ajuste = ajustar(entrenamiento, orden, orden_estacional,
                         exog=x.loc[entrenamiento.index])
        futuro = x.loc[fechas_siguientes(entrenamiento, h)]
        return ajuste.forecast(h, exog=futuro).to_numpy()
    return modelo


def describir_sarimax(serie, orden, estacional, x):
    """Ajusta el SARIMAX con toda la serie para leer el coeficiente de la exógena."""
    titulo("PARTE 4b. SARIMAX con días hábiles")
    print("Días hábiles por mes (sin centrar): mínimo "
          f"{x['dias_habiles'].min() + 21}, máximo {x['dias_habiles'].max() + 21}")
    print("Últimos 12 meses de la serie y 12 meses siguientes:")
    tabla = (x["dias_habiles"] + 21).iloc[-24:]
    print(" ".join(f"{f:%Y-%m}:{v}" for f, v in tabla.items()))
    print("Días hábiles de los meses atípicos frente al promedio de ese mes "
          "en la serie:")
    habiles = x["dias_habiles"].loc[serie.index] + 21
    for fecha, z in detectar_atipicos(serie)["z"].items():
        promedio = habiles[habiles.index.month == fecha.month].mean()
        print(f"  {fecha:%Y-%m}: z = {z:+.1f}, {habiles[fecha]} días hábiles "
              f"(promedio de ese mes: {promedio:.1f})")
    ajuste = ajustar(serie, orden, estacional, exog=x.loc[serie.index])
    coef, ee, pv =(ajuste.params["dias_habiles"], ajuste.bse["dias_habiles"],
                    ajuste.pvalues["dias_habiles"])
    print(f"Coeficiente de dias_habiles: {coef:.4f} (error estándar {ee:.4f}, "
          f"p = {pv:.4g})")
    print(f"AIC del SARIMAX con toda la serie: {ajuste.aic:.2f} "
          f"(BIC {ajuste.bic:.2f})")
    resid = ajuste.resid.iloc[orden[1] + estacional[1] * PERIODO:]
    lb = acorr_ljungbox(resid, lags=[12, 24],
                        model_df=orden[0] + orden[2] + estacional[0] + estacional[2])
    lb.index.name = "rezago"
    print("Ljung-Box de los residuos del SARIMAX:")
    print(lb.round(4).to_string())


# ============================================================
# 5. La tabla de métricas
# ============================================================
POR_ORIGEN = {}


def fila(nombre, serie, modelo):
    por_origen, promedio = backtest(serie, modelo)
    POR_ORIGEN[nombre] = por_origen
    return {"modelo": nombre, "decision": DECISION,
            "RMSE": round(promedio["RMSE"], 2), "MAE": round(promedio["MAE"], 2),
            "MAPE": round(promedio["MAPE"], 2)}


def pendiente(parte, error):
    print(f"  pendiente: {parte} ({error})")


def graficar_backtest(serie, modelos):
    """RMSE por origen de cada modelo y el pronóstico desde el primer y el último origen."""
    largo = pd.concat({n: t.set_index("origen")["RMSE"]
                       for n, t in POR_ORIGEN.items()}, axis=1)
    largo.index = largo.index.strftime("%Y-%m")
    largo.round(3).to_csv(RESULTADOS / "rmse_por_origen.csv",
                          index_label="origen")
    print("\nRMSE por origen del backtest:")
    print(largo.round(2).to_string())

    figura, ejes = plt.subplots(1, 2, figsize=(12, 4))
    for nombre in largo.columns:
        ejes[0].plot(largo.index, largo[nombre], marker="o", label=nombre)
    ejes[0].set_title("RMSE por origen (horizonte 1 a 12)")
    ejes[0].set_xlabel("origen (último mes de entrenamiento)")
    ejes[0].tick_params(axis="x", rotation=60)
    ejes[0].legend(fontsize=7)

    corte = len(serie) - 24
    ejes[1].plot(serie.index[-48:], serie.iloc[-48:].to_numpy(),
                 color="black", label="real")
    entrenamiento = serie.iloc[:corte]
    fechas = fechas_siguientes(entrenamiento, 12)
    for nombre, modelo in modelos.items():
        ejes[1].plot(fechas, modelo(entrenamiento, 12), ls="--", label=nombre)
    ejes[1].axvline(serie.index[corte - 1], color="grey", ls=":")
    ejes[1].set_title(f"Pronóstico desde el primer origen "
                      f"({serie.index[corte - 1]:%Y-%m})")
    ejes[1].legend(fontsize=7)
    figura.tight_layout()
    figura.savefig(FIGURAS / "backtest.png", dpi=120)
    plt.close(figura)


def main():
    titulo("PARTE 1. La serie")
    cruda = cargar_serie(ARCHIVO, FECHA, VALOR)
    print(f"Serie: {len(cruda)} meses, de {cruda.index[0]:%Y-%m} a "
          f"{cruda.index[-1]:%Y-%m}, {cruda.isna().sum()} vacíos")
    print(f"Mínimo {cruda.min():.3f} ({cruda.idxmin():%Y-%m}), máximo "
          f"{cruda.max():.3f} ({cruda.idxmax():%Y-%m}), media {cruda.mean():.3f}")
    serie = preparar(cruda)
    graficar_serie(serie)

    titulo("PARTE 1b. Líneas base en el backtest común")
    primero = len(serie) - 24
    print(f"Backtest: origen móvil sobre los últimos 24 meses, horizonte 1 a 12. "
          f"Orígenes: {serie.index[primero - 1]:%Y-%m} a "
          f"{serie.index[len(serie) - 12 - 1]:%Y-%m} "
          f"({len(serie) - 12 - primero + 1} orígenes); meses pronosticados: "
          f"{serie.index[primero]:%Y-%m} a {serie.index[-1]:%Y-%m}")
    modelos = {"ingenuo": ingenuo,
               "estacional ingenuo": lambda t, h: estacional_ingenuo(t, h, PERIODO)}
    filas = [fila(nombre, serie, m) for nombre, m in modelos.items()]
    print(pd.DataFrame(filas).drop(columns="decision").to_string(index=False))

    try:
        descomponer(serie)
    except NotImplementedError as error:
        pendiente("parte 2", error)

    try:
        d, D = estacionariedad(serie)
    except NotImplementedError as error:
        pendiente("parte 3", error)
        d = D = None

    if d is not None:
        try:
            orden, estacional = elegir_sarima(serie, d, D)
            nombre = f"SARIMA{orden}{estacional}"
            modelos[nombre] = modelo_sarima(orden, estacional)
            filas.append(fila(nombre, serie, modelos[nombre]))
            x = exogenas(serie)
            describir_sarimax(serie, orden, estacional, x)
            nombre = f"SARIMAX{orden}{estacional} + exógenas"
            modelos[nombre] = modelo_sarimax(orden, estacional, x)
            filas.append(fila(nombre, serie, modelos[nombre]))
        except NotImplementedError as error:
            pendiente("parte 4", error)

    titulo("PARTE 5. Tabla de métricas (backtest común, ordenada por RMSE)")
    tabla = pd.DataFrame(filas).sort_values("RMSE")
    tabla.to_csv(RESULTADOS / "metricas.csv", index=False)
    print(tabla.drop(columns="decision").to_string(index=False))
    print("Mejor modelo por RMSE:", tabla.iloc[0]["modelo"])

    bases = tabla[tabla["modelo"].isin(["ingenuo", "estacional ingenuo"])]
    mejor_base = bases.iloc[0]
    mejor = tabla.iloc[0]
    print(f"Mejor línea base: {mejor_base['modelo']}")
    for metrica in ["RMSE", "MAE", "MAPE"]:
        mejora = 100 * (1 - mejor[metrica] / mejor_base[metrica])
        print(f"  {metrica}: {mejor_base[metrica]:.2f} -> {mejor[metrica]:.2f} "
              f"({mejora:.1f} % menos)")
    sarima = tabla[tabla["modelo"].str.startswith("SARIMA(")]
    sarimax = tabla[tabla["modelo"].str.startswith("SARIMAX(")]
    if len(sarima) and len(sarimax):
        print("Efecto de la exógena (SARIMA -> SARIMAX):")
        for metrica in ["RMSE", "MAE", "MAPE"]:
            antes, despues = sarima.iloc[0][metrica], sarimax.iloc[0][metrica]
            print(f"  {metrica}: {antes:.2f} -> {despues:.2f} "
                  f"({100 * (1 - despues / antes):.1f} % menos)")

    graficar_backtest(serie, modelos)


if __name__ == "__main__":
    main()
