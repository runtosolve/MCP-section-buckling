include(joinpath(@__DIR__, "backend", "setup.jl"))

const ROUTER = HTTP.Router()
register_all(ROUTER)

const PORT = parse(Int, get(ENV, "PORT", "8081"))

@info "Running warmups to trigger JIT compilation..."
run_warmups()
@info "Warmups complete — JIT compiled"

@info "CEE Buckling API listening on :$PORT"
HTTP.serve(ROUTER, "0.0.0.0", PORT)
