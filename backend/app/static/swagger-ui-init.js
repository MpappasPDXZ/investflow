// Auto-capture token from login response and auto-authorize
window.addEventListener('load', function() {
    // Wait for Swagger UI to load
    setTimeout(function() {
        if (window.ui) {
            // Intercept login response to auto-capture token
            const originalFetch = window.fetch;
            window.fetch = function(...args) {
                return originalFetch.apply(this, args).then(response => {
                    // Clone response to read it
                    const clonedResponse = response.clone();
                    
                    // Check if this is the login endpoint
                    if (args[0] && args[0].includes('/auth/login') && response.ok) {
                        clonedResponse.json().then(data => {
                            if (data.access_token) {
                                // Auto-authorize with the token
                                window.ui.authActions.authorize({
                                    HTTPBearer: {
                        name: "HTTPBearer",
                        schema: {
                            type: "http",
                            scheme: "bearer",
                            bearerFormat: "JWT"
                        },
                        value: data.access_token
                    }
                                });
                                
                                // Show notification
                                console.log('✅ Auto-authorized with token from login!');
                                
                                // Refresh the page to show authorized state
                                setTimeout(() => {
                                    window.location.reload();
                                }, 500);
                            }
                        }).catch(() => {});
                    }
                    
                    return response;
                });
            };
        }
    }, 1000);
});

