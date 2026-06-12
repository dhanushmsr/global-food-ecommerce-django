# global-food-ecommerce-django
A Django e-commerce framework featuring server-side international phone data normalization, multi-language session state handling, multi-channel OTP security matrices (SMS/SMTP), and low-latency asynchronous checkout pipelines.
📌 Project Title
A Cross-Border E-Commerce Framework featuring International Data Normalization and Multi-Language Session Handling

📝 Abstract / Synopsis
This project presents the design and implementation of a robust, production-grade full-stack e-commerce framework optimized for cross-border gastronomy operations. Built using Python, the Django web framework, and a clean Bootstrap frontend ecosystem, the platform addresses critical real-world engineering challenges in internationalization, data consistency, and low-latency system automation.

The application serves a localized European customer base with a dynamic, dual-language interface (German/English) while seamlessly handling cross-border administrative and security operations. Key technical milestones include a rule-based international data normalization pipeline for mobile communications, custom multi-channel transaction verification (SMS/SMTP OTP matrices), localized multi-tax (Split VAT) financial calculation engines, and an asynchronous, multi-threaded worker framework to eliminate runtime checkout bottlenecks.

⚙️ Core Technical Features & Architecture
1. Multi-Language Session State Persistence
To support cross-border accessibility, the system avoids static views in favor of a dynamic translation architecture. Utilizing Django session backends, the framework tracks user language preferences (en/de) across state boundaries. This preference modifies the rendering layer in real-time, dynamically mapping database fields (e.g., localized food names and descriptions) and alert strings based on the active session footprint without requiring page reloads or broken URL states.

2. International Input Data Normalization
A major challenge in cross-border platforms is format pollution from varying regional inputs. This framework implements a server-side sanitization matrix that intercepts user mobile inputs from different country calling networks (such as India's +91 and Germany's +49). The engine handles input discrepancies—stripping accidental leading zeros, handling local dialing habits, and prepending standardized E.164 international prefixes. This ensures data uniformity before storage and prevents execution dropped exceptions when communicating with third-party telecommunication routing gateways (Twilio).

3. Dual-Channel Volatile Security Matrix
User identity security and fraud mitigation are managed via an on-demand, multi-channel verification pipeline. Upon customer lifecycle initialization or password recovery request, the system instantly generates cryptographically secure, volatile 6-digit OTP tokens bound to a strict 10-minute expiration window. The framework executes a parallel dispatch matrix: routing code parameters simultaneously via an online SMTP server relay for email verification and a virtual cellular API gateway (Twilio) for direct mobile SMS delivery.

4. Compliant Split-VAT Computation Engine
Operating inside European trade zones requires compliance with distinct taxation rules. The framework features an integrated financial processing module that calculates tax subtractions on orders containing mixed inventory items. It dynamically parses line-item breakdown objects to apply a split German Value Added Tax (VAT)—assessing a standard 19% VAT for beverages and a reduced 7% VAT for food items—computed accurately using systematic discount ratios post-coupon redemption to maintain absolute database and invoice ledger integrity.

5. Asynchronous Multi-Threaded Notification Engine
To preserve ultra-low latency profiles and prevent user interface freezing during critical checkout transitions, the application decouples heavy input/output network operations from the main HTTP request-response thread. When an order is committed to the database, a separate, asynchronous background worker thread (threading.Thread) is spawned to handle HTML invoice parsing and SMTP dispatch operations, allowing the frontend client to transition instantly to their billing summary page without server-side performance lag.

🛠️ Technology Stack
Backend Framework: Python, Django 5.2 (Web Framework & MVC Pattern)

Database Architecture: SQLite (Relational structure with strict One-to-One and ForeignKey cascade triggers)

Frontend Design Matrix: HTML5, CSS3, JavaScript (ES6), Bootstrap 5.3, Bootstrap Icons

Third-Party Service Integrations: Twilio REST API SDK (Cellular Routing), SMTP Relay Gateway (Live Email Transmission), OpenStreetMap Nominatim API (Reverse-Geocoding Logistics Layouts)
