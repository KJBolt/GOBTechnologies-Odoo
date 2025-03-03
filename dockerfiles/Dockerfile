FROM odoo:17

# Ensure dependencies can be installed
USER root  

# Ensure dbfilter is correctly configured
RUN echo "dbfilter = .*" >> /etc/odoo/odoo.conf

# Switch back to Odoo user for security
USER odoo  