from netqasm.sdk.epr_socket import EPRSocket, EPRType
from netqasm.sdk.external import NetQASMConnection


def main(app_config=None):
    log_config = app_config.log_config

    epr_socket = EPRSocket("server")

    client = NetQASMConnection(
        app_name=app_config.app_name,
        log_config=log_config,
        epr_sockets=[epr_socket],
        # return_arrays=False,
    )

    with client:
        num_pairs = 10
        outcomes = client.new_array(num_pairs)

        def post_create(conn, q, pair):
            array_entry = outcomes.get_future_index(pair)
            # store measurement outcome in array
            q.measure(array_entry)

        # Create EPR pair
        epr_socket.create(
            number=num_pairs,
            tp=EPRType.K,
            sequential=True,
            post_routine=post_create,
        )

    bits = "".join([str(outcome) for outcome in outcomes])
    print(bits)


if __name__ == "__main__":
    main()
