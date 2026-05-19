using CeeSectionBucklingAPI: perform_calculation

function handle_cee_section_calculate(req::HTTP.Request)
    local body
    try
        body = JSON3.read(String(req.body))
    catch e
        return error_response(400, "Invalid JSON: $(e)")
    end

    try
        E = Float64(get(body, :E, 203000.0))   # Young's modulus (MPa)
        ν = Float64(get(body, :nu, 0.3))        # Poisson's ratio
        t = Float64(get(body, :t, 1.0))         # thickness (mm)
        L = Float64(get(body, :L, 15.0))        # lip dimension (mm)
        B = Float64(get(body, :B, 50.0))        # flange width (mm)
        H = Float64(get(body, :H, 100.0))       # web height (mm)
        r = Float64(get(body, :r, 2.0))         # inside radius (mm)
        mode_shape_element_discretization = Int(get(body, :mode_shape_element_discretization, 5))

        inputs_path = tempname() * ".json"
        outputs_path = tempname() * ".json"

        open(inputs_path, "w") do f
            JSON3.write(f, (; E, ν, t, L, B, H, r, mode_shape_element_discretization))
        end

        perform_calculation(inputs_path, outputs_path)

        result = JSON3.read(read(outputs_path, String))

        rm(inputs_path, force=true)
        rm(outputs_path, force=true)

        response = (
            Pcrl  = result.Pcrℓ,
            Pcrd  = result.Pcrd,
            units = "N",
            inputs = (; E, nu=ν, t, L, B, H, r, mode_shape_element_discretization),
        )

        if hasproperty(result, :local_buckling_mode_shape)
            response = merge(response, (
                local_buckling_mode_shape = result.local_buckling_mode_shape,
                distortional_buckling_mode_shape = result.distortional_buckling_mode_shape,
            ))
        end

        if hasproperty(result, :section_properties)
            response = merge(response, (section_properties = result.section_properties,))
        end

        return json_response(200, response)
    catch e
        @error "Calculation error" exception=(e, catch_backtrace())
        return error_response(500, "Calculation failed: $(e)")
    end
end

function register_calculate_cee_section!(router::HTTP.Router)
    HTTP.register!(router, "POST",    "/calculate_cee_section", handle_cee_section_calculate)
    HTTP.register!(router, "OPTIONS", "/calculate_cee_section", handle_cors)
end

function warmup_calculate_cee_section!()
    warmup_in  = tempname() * ".json"
    warmup_out = tempname() * ".json"
    open(warmup_in, "w") do f
        JSON3.write(f, (; E=203000.0, ν=0.3, t=1.0, L=15.0, B=50.0, H=100.0, r=2.0,
                          mode_shape_element_discretization=5))
    end
    perform_calculation(warmup_in, warmup_out)
    rm(warmup_in, force=true)
    rm(warmup_out, force=true)
end
