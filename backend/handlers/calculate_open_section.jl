using OpenSectionBucklingAPI: perform_calculation as perform_open_section_calculation

function handle_open_section_calculate(req::HTTP.Request)
    local body
    try
        body = JSON3.read(String(req.body))
    catch e
        return error_response(400, "Invalid JSON: $(e)")
    end

    try
        E = Float64(get(body, :E, 29500.0))
        ν = Float64(get(body, :nu, 0.3))
        t = Float64(get(body, :t, 0.102))

        coords_in = get(body, :coordinates, (X = [0.0, 1.0, 2.0, 3.0, 4.0],
                                             Y = [0.0, 2.0, 6.0, 8.0, 3.0]))
        X = Float64.(collect(coords_in.X))
        Y = Float64.(collect(coords_in.Y))
        coordinates = (X = X, Y = Y)

        centerline_radius = Float64(get(body, :centerline_radius, 2 * t))

        loads_in = get(body, :loads, (P = 1.0, Mxx = 0.0, Mzz = 0.0, M11 = 0.0, M22 = 0.0))
        loads = (
            P   = Float64(get(loads_in, :P,   0.0)),
            Mxx = Float64(get(loads_in, :Mxx, 0.0)),
            Mzz = Float64(get(loads_in, :Mzz, 0.0)),
            M11 = Float64(get(loads_in, :M11, 0.0)),
            M22 = Float64(get(loads_in, :M22, 0.0)),
        )

        load_type = String(get(body, :load_type, "P"))

        flat_mesh_size_goal   = Float64(get(body, :flat_mesh_size_goal, 0.5))
        corner_mesh_size_goal = Float64(get(body, :corner_mesh_size_goal, π / 6))

        mode_shape_element_discretization = Int(get(body, :mode_shape_element_discretization, 2))

        inputs_path  = tempname() * ".json"
        outputs_path = tempname() * ".json"

        open(inputs_path, "w") do f
            JSON3.write(f, (;
                E, ν, t,
                coordinates,
                centerline_radius,
                loads,
                load_type,
                flat_mesh_size_goal,
                corner_mesh_size_goal,
                mode_shape_element_discretization,
            ))
        end

        perform_open_section_calculation(inputs_path, outputs_path)

        result = JSON3.read(read(outputs_path, String))

        rm(inputs_path, force=true)
        rm(outputs_path, force=true)

        response = (
            local_buckling_label             = result.local_buckling_label,
            distortional_buckling_label      = result.distortional_buckling_label,
            Lcrl                             = result.Lcrℓ,
            Lcrd                             = result.Lcrd,
            Rcrl                             = result.Rcrℓ,
            Rcrd                             = result.Rcrd,
            local_buckling_mode_shape        = result.local_buckling_mode_shape,
            distortional_buckling_mode_shape = result.distortional_buckling_mode_shape,
            section_properties               = result.section_properties,
            inputs = (;
                E, nu = ν, t,
                coordinates,
                centerline_radius,
                loads,
                load_type,
                flat_mesh_size_goal,
                corner_mesh_size_goal,
                mode_shape_element_discretization,
            ),
        )

        return json_response(200, response)
    catch e
        @error "Open section calculation error" exception=(e, catch_backtrace())
        return error_response(500, "Calculation failed: $(e)")
    end
end

function register_calculate_open_section!(router::HTTP.Router)
    HTTP.register!(router, "POST",    "/calculate_open_section", handle_open_section_calculate)
    HTTP.register!(router, "OPTIONS", "/calculate_open_section", handle_cors)
end

function warmup_calculate_open_section!()
    warmup_in  = tempname() * ".json"
    warmup_out = tempname() * ".json"
    open(warmup_in, "w") do f
        JSON3.write(f, (;
            E = 29500.0,
            ν = 0.30,
            t = 0.102,
            coordinates = (X = [0.0, 1.0, 2.0, 3.0, 4.0],
                           Y = [0.0, 2.0, 6.0, 8.0, 3.0]),
            centerline_radius = 2 * 0.102,
            loads = (P = 1.0, Mxx = 0.0, Mzz = 0.0, M11 = 0.0, M22 = 0.0),
            load_type = "P",
            flat_mesh_size_goal = 0.5,
            corner_mesh_size_goal = π / 6,
            mode_shape_element_discretization = 2,
        ))
    end
    perform_open_section_calculation(warmup_in, warmup_out)
    rm(warmup_in, force=true)
    rm(warmup_out, force=true)
end
