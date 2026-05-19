using HTTP
using JSON3

const CORS_HEADERS = [
    "Content-Type"                 => "application/json",
    "Access-Control-Allow-Origin"  => "*",
    "Access-Control-Allow-Methods" => "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers" => "Content-Type",
]

function json_response(status::Int, body)
    HTTP.Response(status, CORS_HEADERS, JSON3.write(body))
end

function error_response(status::Int, message::String)
    json_response(status, (error = message,))
end

function handle_cors(::HTTP.Request)
    HTTP.Response(204, CORS_HEADERS)
end

# Each handler file must define a `register!(router)` function and may
# optionally define a `warmup!()` function. Names are namespaced by
# prefixing with the handler key below.
const HANDLERS = [
    (key = :health,                   file = "handlers/health.jl"),
    (key = :calculate_cee_section,    file = "handlers/calculate_cee_section.jl"),
]

for h in HANDLERS
    include(joinpath(@__DIR__, h.file))
end

function register_all(router::HTTP.Router)
    for h in HANDLERS
        fn = getfield(@__MODULE__, Symbol("register_", h.key, "!"))
        fn(router)
    end
end

function run_warmups()
    for h in HANDLERS
        name = Symbol("warmup_", h.key, "!")
        if isdefined(@__MODULE__, name)
            @info "Running warmup: $name"
            getfield(@__MODULE__, name)()
        end
    end
end
