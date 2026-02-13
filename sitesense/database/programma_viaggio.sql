CREATE TABLE programs (
    id INT AUTO_INCREMENT PRIMARY KEY, 
    user_id INT NOT NULL,
    city_id INT NOT NULL,
    num_locali INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (city_id) REFERENCES cities(id) ON DELETE CASCADE
);



INSERT INTO programs (id, user_id, city_id, num_locali) VALUES
    (1, 1, 1, 5),
    (2, 2, 1, 3),
    (3, 3, 2, 2);
    
 SELECT * FROM programs;   