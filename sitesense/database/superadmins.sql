CREATE TABLE superadmins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(100) NOT NULL
    );


INSERT INTO superadmins (id, username, email, password) VALUES
('1', 'super_admin_160',  'super.admin2000@gmail.com', '$2b$12$KhOj0txV1xO.nIDQ8M7K3emlky9llZUAlpEzRezyCDaxG05yDGa7C')


