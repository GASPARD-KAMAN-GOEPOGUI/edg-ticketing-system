"""Connexion MySQL réglée en UTC (= heure de Guinée), quel que soit le fuseau du
serveur : en production l'hébergeur est à l'heure de Paris et NOW() / les
valeurs par défaut des colonnes étaient 1 à 2 h en avance (2026-10-14)."""
from api.configs.Database import MYSQL_UTC_INIT_COMMAND, engine_connect_args


def test_mysql_connections_are_forced_to_utc():
    assert engine_connect_args("mysql+aiomysql") == {"init_command": "SET time_zone = '+00:00'"}
    assert MYSQL_UTC_INIT_COMMAND == "SET time_zone = '+00:00'"


def test_other_dialects_untouched():
    assert engine_connect_args("sqlite+aiosqlite") == {}
