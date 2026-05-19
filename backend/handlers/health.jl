function handle_health(::HTTP.Request)
    json_response(200, (
        status    = "ok",
        endpoints = ["/", "/calculate_cee_section"],
    ))
end

function register_health!(router::HTTP.Router)
    HTTP.register!(router, "GET",     "/", handle_health)
    HTTP.register!(router, "OPTIONS", "/", handle_cors)
end
