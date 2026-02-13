

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    google_id VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(100),
    surname VARCHAR(100),
    registration_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    profile_image VARCHAR(255)
);


INSERT INTO users (google_id, email, name, surname, registration_date) VALUES
( '10784567890127456789', 'mario.rossi@gmail.com',  'Mario', 'Rossi', '2025-10-14 10:30:00'),
( '10784567890123456789', 'anna.bianchi@gmail.com', 'Anna', 'Bianchi', '2025-10-13 14:15:00'),
( '10784567898123456789', 'luca.verdi@gmail.com', 'Luca', 'Verdi', '2025-10-15 09:00:00');

