import requests
import pandas as pd
import streamlit as st


@st.cache_data(ttl=3600)

def fetch_brent_spot(API_KEY, frecuencia: str = 'daily', start: str = '2025-01-01'
     ) -> pd.DataFrame:
    # 1. Cargar entorno y credenciales primero
    if not API_KEY:
        print("Error: No se encontró la API Key.")
        raise RuntimeError("Falta EIA_API_KEY")

    # 2. Configurar la URL correcta para Petróleo (Brent)
    URL_BASE = "https://api.eia.gov/v2/petroleum/pri/spt/data/"
    
    # 3. Construir el diccionario de parámetros AQUÍ (así puede usar API_KEY)
    parametros = {
        'api_key': API_KEY,
        'frequency': frecuencia,
        'data[]': 'value',
        'facets[series][]': 'RBRTE',  # ID típico del Brent de la EIA
        'start': start,
        'sort[0][column]': 'period',
        'sort[0][direction]': 'asc'
    }

    # 4. Realizar la petición HTTP GET
    respuesta = requests.get(URL_BASE, params=parametros)

    # ¡Que grite si falla! Si el status no es 200, raise_for_status() detiene la ejecución
    if respuesta.status_code != 200:
        print(f"❌ Error crítico en la API de EIA. Status: {respuesta.status_code}")
        print(f"Detalle del error: {respuesta.text[:300]}")
        respuesta.raise_for_status() 

    # 5. Procesar la respuesta (Si llega aquí, sabemos que es 200)
    datos_json = respuesta.json()
    
    # Extraer metadatos de control y datos reales
    total_disponible = int(datos_json['response']['total'])
    lista_datos = datos_json['response']['data']
    filas_recibidas = len(lista_datos)

    # 🚨 El Guardia del Límite (estilo ArcGIS/exceededTransferLimit)
    if filas_recibidas < total_disponible:
        print(f"⚠️ ¡ATENCIÓN! Datos truncados por la API. Recibidos: {filas_recibidas} de {total_disponible} totales.")
        print("Sugerencia: Acota el parámetro 'start' o implementa paginación.")

    # Convertir a DataFrame y retornar
    df = pd.DataFrame(lista_datos)
    return df

@st.cache_data(ttl=3600)

def fetch_spr_stocks(API_KEY, frecuencia: str = 'weekly', start: str = '2025-01-01'
     ) -> pd.DataFrame:
    # 1. Cargar entorno y credenciales primero
    
    if not API_KEY:
        print("Error: No se encontró la API Key.")
        raise RuntimeError("Falta EIA_API_KEY")

    # 2. Configurar la URL para reservas de crudo EEUU (serie semanal)
    URL_BASE = "https://api.eia.gov/v2/petroleum/stoc/wstk/data/"

    # 3. Construir el diccionario de parámetros AQUÍ (así puede usar API_KEY)
    parametros = {
        'api_key': API_KEY,
        'frequency': frecuencia,
        'data[]': 'value',
        'facets[series][]': 'WCSSTUS1',  # Reservas estratégicas de crudo EEUU - SPR (miles de barriles)
        'start': start,
        'sort[0][column]': 'period',
        'sort[0][direction]': 'asc'
    }

    # 4. Realizar la petición HTTP GET
    respuesta = requests.get(URL_BASE, params=parametros)

    # ¡Que grite si falla! Si el status no es 200, raise_for_status() detiene la ejecución
    if respuesta.status_code != 200:
        print(f"❌ Error crítico en la API de EIA. Status: {respuesta.status_code}")
        print(f"Detalle del error: {respuesta.text[:300]}")
        respuesta.raise_for_status() 

    # 5. Procesar la respuesta (Si llega aquí, sabemos que es 200)
    datos_json = respuesta.json()
    
    # Extraer metadatos de control y datos reales
    total_disponible = int(datos_json['response']['total'])
    lista_datos = datos_json['response']['data']
    filas_recibidas = len(lista_datos)

    # 🚨 El Guardia del Límite (estilo ArcGIS/exceededTransferLimit)
    if filas_recibidas < total_disponible:
        print(f"⚠️ ¡ATENCIÓN! Datos truncados por la API. Recibidos: {filas_recibidas} de {total_disponible} totales.")
        print("Sugerencia: Acota el parámetro 'start' o implementa paginación.")

    # Convertir a DataFrame y retornar
    df = pd.DataFrame(lista_datos)
    return df

@st.cache_data(ttl=3600)

def fetch_comercial_stocks(API_KEY, frecuencia: str = 'weekly', start: str = '2025-01-01'
     ) -> pd.DataFrame:
    # 1. Cargar entorno y credenciales primero
    
    if not API_KEY:
        print("Error: No se encontró la API Key.")
        raise RuntimeError("Falta EIA_API_KEY")

    # 2. Configurar la URL para reservas de crudo EEUU (serie semanal)
    URL_BASE = "https://api.eia.gov/v2/petroleum/stoc/wstk/data/"

    # 3. Construir el diccionario de parámetros AQUÍ (así puede usar API_KEY)
    parametros = {
        'api_key': API_KEY,
        'frequency': frecuencia,
        'data[]': 'value',
        'facets[series][]': 'WCESTUS1',  # Reservas crudo comercial EEUU (miles de barriles)
        'start': start,
        'sort[0][column]': 'period',
        'sort[0][direction]': 'asc'
    }

    # 4. Realizar la petición HTTP GET
    respuesta = requests.get(URL_BASE, params=parametros)

    # ¡Que grite si falla! Si el status no es 200, raise_for_status() detiene la ejecución
    if respuesta.status_code != 200:
        print(f"❌ Error crítico en la API de EIA. Status: {respuesta.status_code}")
        print(f"Detalle del error: {respuesta.text[:300]}")
        respuesta.raise_for_status() 

    # 5. Procesar la respuesta (Si llega aquí, sabemos que es 200)
    datos_json = respuesta.json()
    
    # Extraer metadatos de control y datos reales
    total_disponible = int(datos_json['response']['total'])
    lista_datos = datos_json['response']['data']
    filas_recibidas = len(lista_datos)

    # 🚨 El Guardia del Límite (estilo ArcGIS/exceededTransferLimit)
    if filas_recibidas < total_disponible:
        print(f"⚠️ ¡ATENCIÓN! Datos truncados por la API. Recibidos: {filas_recibidas} de {total_disponible} totales.")
        print("Sugerencia: Acota el parámetro 'start' o implementa paginación.")

    # Convertir a DataFrame y retornar
    df = pd.DataFrame(lista_datos)
    return df