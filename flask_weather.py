import requests
from flask import Flask, request, render_template
import plotly.graph_objs as go
from dash import Dash, dcc, html as dash_html, Input, Output
import pandas as pd

class MeteoService:
    search_url = 'http://dataservice.accuweather.com/locations/v1/cities/search'
    forecast_1_url = 'http://dataservice.accuweather.com/forecasts/v1/daily/1day/'
    forecast_5_url = 'http://dataservice.accuweather.com/forecasts/v1/daily/5day/'

    def __init__(self, key):
        self.key = key

    def fetch_coordinates(self, location):
        try:
            params = {'apikey': self.key, 'q': location}
            response = requests.get(self.search_url, params=params)
            response.raise_for_status()
            data = response.json()[0]['GeoPosition']
            return data['Latitude'], data['Longitude']
        except requests.exceptions.ConnectionError:
            raise ConnectionError("Не удалось подключиться к серверу")
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                raise ValueError('Неправильные данные')
            elif response.status_code == 503:
                raise PermissionError('API не работают')
            else:
                raise PermissionError('Доступ запрещен')
        except Exception as e:
            raise Exception(f'Ошибка: {e}')

    def fetch_city_key(self, location):
        try:
            params = {'apikey': self.key, 'q': location}
            response = requests.get(self.search_url, params=params)
            response.raise_for_status()
            return response.json()[0]['Key']
        except requests.exceptions.ConnectionError:
            raise ConnectionError("Не удалось подключиться к серверу")
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                raise ValueError('Неправильные данные')
            elif response.status_code == 503:
                raise PermissionError('API не работают')
            else:
                raise PermissionError('Доступ запрещен')
        except Exception as e:
            raise Exception(f'Ошибка: {e}')

    def fetch_forecast(self, key, period):
        try:
            params = {'apikey': self.key, 'details': 'true', 'metric': 'true'}
            url = self.forecast_1_url + key if period == '1day' else self.forecast_5_url + key
            response = requests.get(url, params=params)
            if response.status_code not in [200, 401]:
                response.raise_for_status()
            data = response.json()
            forecasts = []
            days = 1 if period == '1day' else 5
            for i in range(days):
                day_data = data['DailyForecasts'][i]
                forecast = {
                    'date': day_data['Date'][:10],
                    'temp': day_data['RealFeelTemperatureShade']['Minimum']['Value'],
                    'humidity': day_data['Day']['RelativeHumidity']['Average'],
                    'speed_wind': day_data['Day']['Wind']['Speed']['Value'],
                    'probability': day_data['Day']['PrecipitationProbability']
                }
                forecasts.append(forecast)
            return forecasts
        except requests.exceptions.ConnectionError:
            raise ConnectionError("Не удалось подключиться к серверу")
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                raise ValueError('Неправильные данные')
            elif response.status_code == 503:
                raise PermissionError('API не работают')
            else:
                raise PermissionError('Доступ запрещен')
        except Exception as e:
            raise Exception(f'Произошла неизвестная ошибка: {e}')

    def analyze_conditions(self, temperature, humidity, wind_speed, precipitation_prob):
        analysis = []
        level = 1
        if temperature > 30:
            analysis.append('На улице нереально жарко, лучше не выходить.')
            level = 3
        elif 15 <= temperature <= 30:
            analysis.append('Температура приятная.')
        elif 0 <= temperature < 15:
            analysis.append('Прохладно.')
            level = 2
        elif -10 <= temperature < 0:
            analysis.append('Холодно, наденьте куртку!')
            level = 2
        else:
            analysis.append('Очень холодно! Не выходите.')
            level = 3

        if humidity > 85:
            if temperature > 30:
                analysis.append('Высокая влажность и температура - возьмите зон.')
                level = 3
            elif temperature < 0:
                analysis.append('Гололед.')
                level = max(level, 2)
        elif humidity < 30:
            analysis.append('Низкая влажность. Риск сухости в горле, глазах, носу.')
            level = max(level, 2)

        if wind_speed > 40:
            if precipitation_prob > 80:
                analysis.append('Сильный ветер и осадки. Скорее всего будет ураган.')
                level = 3
            else:
                analysis.append('Сильный ветер.')
                level = max(level, 2)
        elif 20 < wind_speed <= 40:
            analysis.append('Ветер.')
            level = max(level, 2)

        if precipitation_prob > 80:
            if temperature > 25:
                analysis.append('Жарко и высокая вероятность осадков. Возможен ураган.')
                level = 3
            elif temperature < 0:
                analysis.append('Холодно и высокая вероятность осадков. Возможен гололед и град.')
                level = 3
        elif precipitation_prob > 50:
            analysis.append('Большая вероятность дождя.')
            level = max(level, 2)
        elif precipitation_prob > 20:
            analysis.append('Возможен дождь.')
            level = max(level, 1)

        if level == 3:
            analysis.append('Так себе')
        elif level == 2:
            analysis.append('Пойдет')
        else:
            analysis.append('Хорошая')

        return analysis

app = Flask(__name__)
city_data = {}
forecast_day = ''
dash_plot = Dash(__name__, server=app, url_base_pathname='/plot/')
dash_map = Dash(__name__, server=app, url_base_pathname='/map/')

api_key = 'wckF5UHNomgSXpNEfxaHyMRdwIXhiken'
meteo = MeteoService(api_key)

dash_plot.layout = dash_html.Div([
    dcc.Dropdown(
        id='parameter-dropdown',
        options=[
            {'label': 'Температура', 'value': 'temp'},
            {'label': 'Скорость ветра', 'value': 'speed_wind'},
            {'label': 'Влажность', 'value': 'humidity'},
            {'label': 'Вероятность осадков', 'value': 'probability'}
        ],
        value='temp'
    ),
    dcc.Graph(id='weather-graph')
])

dash_map.layout = dash_html.Div([
    dcc.Graph(id='temperature-map')
])

@dash_plot.callback(Output('weather-graph', 'figure'), Input('parameter-dropdown', 'value'))
def update_graph(selected_param):
    figure = go.Figure()
    labels = {
        'temp': 'Температура',
        'speed_wind': 'Скорость ветра',
        'humidity': 'Влажность',
        'probability': 'Вероятность осадков'
    }
    global city_data, forecast_day
    for city, forecasts in city_data.items():
        if forecast_day == '1day':
            figure.add_trace(go.Bar(
                x=[city],
                y=[forecasts[0][selected_param]],
                name=f"{labels[selected_param]} в {city}"
            ))
            figure.update_layout(
                title="Визуализация погоды для городов",
                xaxis_title='Город',
                yaxis_title='Значение',
                showlegend=True,
                barmode='group',
                template='plotly_white'
            )
        elif forecast_day in ['3day', '5day']:
            days = 3 if forecast_day == '3day' else 5
            figure.add_trace(go.Scatter(
                x=[forecasts[i]['date'] for i in range(days)],
                y=[forecasts[i][selected_param] for i in range(days)],
                mode='lines+markers',
                name=f"{labels[selected_param]} в {city}"
            ))
            figure.update_layout(
                title="Визуализация погоды для городов",
                xaxis_title='Дата',
                yaxis_title='Значение',
                showlegend=True,
                template='plotly_white'
            )
    return figure

@dash_map.callback(Output('temperature-map', 'figure'), Input('temperature-map', 'id'))
def generate_map(_):
    global city_data, meteo
    latitudes = []
    longitudes = []
    cities = []
    temperatures = []
    for city, forecasts in city_data.items():
        cities.append(city)
        temperatures.append(f"Температура в {city}: {forecasts[0]['temp']}")
        coords = meteo.fetch_coordinates(city)
        latitudes.append(coords[0])
        longitudes.append(coords[1])
    df = pd.DataFrame({
        'Город': cities,
        'lat': latitudes,
        'lon': longitudes,
        'Температура': temperatures
    })
    map_fig = go.Figure()
    map_fig.add_trace(go.Scattermapbox(
        lat=df['lat'],
        lon=df['lon'],
        hovertext=df['Температура'],
        marker=dict(size=10, color='red'),
        mode='markers'
    ))
    map_fig.update_layout(
        mapbox=dict(
            style='open-street-map',
            zoom=3,
            center={'lat': 55.752, 'lon': 37.619}
        ),
        height=500
    )
    return map_fig

@app.route('/', methods=['GET', 'POST'])
def weather_route():
    global city_data, forecast_day
    city_data = {}
    forecast_day = ''
    if request.method == 'GET':
        return render_template('weather.html')
    else:
        start = request.form['first']
        end = request.form['second']
        additional = request.form
        forecast_day = request.form['day']
        city_data[start] = []
        city_data[end] = []
        for key in additional:
            if key.startswith('city'):
                city_data[additional[key]] = []
        try:
            for city in city_data:
                key = meteo.fetch_city_key(city)
                forecasts = meteo.fetch_forecast(key, forecast_day)
                for forecast in forecasts:
                    analysis = meteo.analyze_conditions(
                        forecast['temp'],
                        forecast['humidity'],
                        forecast['speed_wind'],
                        forecast['probability']
                    )
                    forecast['weather'] = '. '.join(analysis[:-1])
                    forecast['level'] = analysis[-1]
                    city_data[city].append(forecast)
            return render_template('result.html', city_weather=city_data)
        except (ConnectionError, ValueError, PermissionError, Exception) as e:
            return render_template('error.html', error=str(e))

if __name__ == '__main__':
    app.run(debug=True)