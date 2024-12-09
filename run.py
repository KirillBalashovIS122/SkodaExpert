from app import create_app, db
from sqlalchemy import text

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        try:
            print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
            with db.engine.connect() as connection:
                # Преобразуем CURRENT_TIMESTAMP в строку с увеличенной длиной
                result = connection.execute(text("SELECT CAST(CURRENT_TIMESTAMP AS VARCHAR(50)) FROM RDB$DATABASE"))
                current_time = result.fetchone()
                if current_time:
                    print(f"Текущее время в базе данных: {current_time[0]}")
                else:
                    print("Не удалось получить текущее время.")
        except Exception as e:
            print(f"Database connection error: {e}")
    app.run(debug=True)