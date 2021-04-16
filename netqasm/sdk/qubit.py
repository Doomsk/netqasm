"""Qubit representation.

This module contains the `Qubit` class, which are used by application scripts
as handles to in-memory qubits.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from netqasm.lang.ir import GenericInstr
from netqasm.sdk.futures import Future, RegFuture

if TYPE_CHECKING:
    from netqasm.qlink_compat import LinkLayerOKTypeK
    from netqasm.sdk.connection import BaseNetQASMConnection


class QubitNotActiveError(MemoryError):
    pass


class Qubit:
    """Representation of a qubit that has been allocated in the quantum node.

    A `Qubit` instance represents a quantum state that is stored in a physical qubit
    somewhere in the quantum node.
    The particular qubit is identified by its virtual qubit ID.
    To which physical qubit ID this is mapped (at a given time), is handled completely
    by the quantum node controller and is not known to the `Qubit` itself.

    A `Qubit` object can be instantiated in an application script.
    Such an instantiation is automatically compiled into NetQASM instructions that
    allocate and initialize a new qubit in the quantum node controller.

    A `Qubit` object may also be obtained by SDK functions that return them, like
    the `create()` method on an `EPRSocket`, which returns the object as a handle to
    the qubit that is now entangled with one in another node.

    Qubit operations like applying gates and measuring them are done by calling
    methods on a `Qubit` instance.
    """

    def __init__(
        self,
        conn: BaseNetQASMConnection,
        add_new_command: bool = True,
        ent_info: Optional[LinkLayerOKTypeK] = None,
        virtual_address: Optional[int] = None,
    ):
        """Qubit constructor. This is the standard way to allocate a new qubit in
        an application.

        :param conn: connection of the application in which to allocate the qubit
        :param add_new_command: whether to automatically add NetQASM instructions to
            the current subroutine to allocate and initialize the qubit
        :param ent_info: entanglement generation information in case this qubit is
            the result of an entanglement generation request
        :param virtual_address: explicit virtual ID to use for this qubit. If None,
            a free ID is automatically chosen.
        """
        self._conn: BaseNetQASMConnection = conn
        if virtual_address is None:
            self._qubit_id: int = self._conn._builder.new_qubit_id()
        else:
            self._qubit_id = virtual_address

        if add_new_command:
            self._conn._builder.add_new_qubit_commands(qubit_id=self.qubit_id)

        self._active: bool = False
        self._activate()

        self._ent_info: Optional[LinkLayerOKTypeK] = ent_info

        self._remote_ent_node: Optional[str] = None

    def __str__(self) -> str:
        if self.active:
            return "Qubit at the node {}".format(self._conn.node_name)
        else:
            return "Not active qubit"

    @property
    def connection(self) -> BaseNetQASMConnection:
        """Get the NetQASM connection of this qubit"""
        return self._conn

    @property
    def qubit_id(self) -> int:
        """Get the qubit ID"""
        return self._qubit_id

    @qubit_id.setter
    def qubit_id(self, qubit_id: int) -> None:
        assert isinstance(qubit_id, int), "qubit_id should be an int"
        self._qubit_id = qubit_id

    @property
    def active(self) -> bool:
        return self._active

    @active.setter
    def active(self, active: bool) -> None:
        assert isinstance(active, bool), "active shoud be a bool"

        # Check if not already new state
        if self._active == active:
            return

        self._active = active

        if active:
            self._activate()
        else:
            self._deactivate()

    def _activate(self) -> None:
        self._active = True
        if self not in self._conn._builder.active_qubits:
            self._conn._builder.active_qubits.append(self)

    def _deactivate(self) -> None:
        self._active = False
        if self in self._conn._builder.active_qubits:
            self._conn._builder.active_qubits.remove(self)

    @property
    def entanglement_info(self) -> Optional[LinkLayerOKTypeK]:
        """Get the entanglement info"""
        return self._ent_info

    @property
    def remote_entangled_node(self) -> Optional[str]:
        """Get the name of the remote node the qubit is entangled with.
        If not entanled, `None` is returned.
        """
        if self._remote_ent_node is not None:
            return self._remote_ent_node
        if self.entanglement_info is None:
            return None
        # Lookup remote entangled node
        remote_node_id = self.entanglement_info.remote_node_id
        remote_node_name = self._conn.network_info._get_node_name(
            node_id=remote_node_id
        )
        self._remote_ent_node = remote_node_name
        return remote_node_name

    def assert_active(self) -> None:
        """
        Checks if the qubit is active
        """
        if not self.active:
            raise QubitNotActiveError(f"Qubit {self.qubit_id} is not active")

    def measure(
        self,
        future: Optional[Union[Future, RegFuture]] = None,
        inplace: bool = False,
        store_array: bool = True,
    ) -> Union[Future, RegFuture]:
        """Measure the qubit in the standard basis and get the measurement outcome.

        :param future: the `Future` to place the outcome in. If None, a Future is
            created automatically.
        :param inplace: If False, the measurement is destructive and the qubit is
            removed from memory. If True, the qubit is left in the post-measurement
            state.
        :param store_array: whether to store the outcome in an array. If not, it is
            placed in a register. Only used if `future` is None.
        :return: the Future representing the measurement outcome
        """
        self.assert_active()

        if future is None:
            if store_array:
                array = self._conn._builder.new_array(1)
                future = array.get_future_index(0)
            else:
                future = RegFuture(self._conn)

        self._conn._builder.add_measure_commands(
            qubit_id=self.qubit_id,
            future=future,
            inplace=inplace,
        )

        if not inplace:
            self.active = False

        return future

    def X(self) -> None:
        """
        Performs a X on the qubit.
        """
        self._conn._builder.add_single_qubit_commands(
            instr=GenericInstr.X, qubit_id=self.qubit_id
        )

    def Y(self) -> None:
        """
        Performs a Y on the qubit.
        """
        self._conn._builder.add_single_qubit_commands(
            instr=GenericInstr.Y, qubit_id=self.qubit_id
        )

    def Z(self) -> None:
        """
        Performs a Z on the qubit.
        """
        self._conn._builder.add_single_qubit_commands(
            instr=GenericInstr.Z, qubit_id=self.qubit_id
        )

    def T(self) -> None:
        """
        Performs a T gate on the qubit.
        """
        self._conn._builder.add_single_qubit_commands(
            instr=GenericInstr.T, qubit_id=self.qubit_id
        )

    def H(self) -> None:
        """
        Performs a Hadamard on the qubit.
        """
        self._conn._builder.add_single_qubit_commands(
            instr=GenericInstr.H, qubit_id=self.qubit_id
        )

    def K(self) -> None:
        """
        Performs a K gate on the qubit.
        """
        self._conn._builder.add_single_qubit_commands(
            instr=GenericInstr.K, qubit_id=self.qubit_id
        )

    def S(self) -> None:
        """
        Performs a S gate on the qubit.
        """
        self._conn._builder.add_single_qubit_commands(
            instr=GenericInstr.S, qubit_id=self.qubit_id
        )

    def rot_X(self, n: int = 0, d: int = 0, angle: Optional[float] = None):
        """Performs a rotation around the X-axis of an angle `n * pi / 2 ^ d`
        If `angle` is specified `n` and `d` are ignored and a sequence of `n` and `d` are used to approximate the angle.
        """
        self._conn._builder.add_single_qubit_rotation_commands(
            instruction=GenericInstr.ROT_X,
            virtual_qubit_id=self.qubit_id,
            n=n,
            d=d,
            angle=angle,
        )

    def rot_Y(self, n: int = 0, d: int = 0, angle: Optional[float] = None):
        """Performs a rotation around the Y-axis of an angle `n * pi / 2 ^ d`
        If `angle` is specified `n` and `d` are ignored and a sequence of `n` and `d` are used to approximate the angle.
        """
        self._conn._builder.add_single_qubit_rotation_commands(
            instruction=GenericInstr.ROT_Y,
            virtual_qubit_id=self.qubit_id,
            n=n,
            d=d,
            angle=angle,
        )

    def rot_Z(self, n: int = 0, d: int = 0, angle: Optional[float] = None):
        """Performs a rotation around the Z-axis of an angle `n * pi / 2 ^ d`
        If `angle` is specified `n` and `d` are ignored and a sequence of `n` and `d` are used to approximate the angle.
        """
        self._conn._builder.add_single_qubit_rotation_commands(
            instruction=GenericInstr.ROT_Z,
            virtual_qubit_id=self.qubit_id,
            n=n,
            d=d,
            angle=angle,
        )

    def cnot(self, target: Qubit) -> None:
        """
        Applies a cnot onto target.
        Target should be a qubit-object with the same connection.

        Parameters
        ----------
        target : :class:`~.Qubit`
            The target qubit
        """
        self._conn._builder.add_two_qubit_commands(
            instr=GenericInstr.CNOT,
            control_qubit_id=self.qubit_id,
            target_qubit_id=target.qubit_id,
        )

    def cphase(self, target: Qubit) -> None:
        """
        Applies a cphase onto target.
        Target should be a qubit-object with the same connection.

        Parameters
        ----------
        target : :class:`~.Qubit`
            The target qubit
        """
        self._conn._builder.add_two_qubit_commands(
            instr=GenericInstr.CPHASE,
            control_qubit_id=self.qubit_id,
            target_qubit_id=target.qubit_id,
        )

    def reset(self) -> None:
        r"""
        Resets the qubit to the state \|0>
        """
        self._conn._builder.add_init_qubit_commands(qubit_id=self.qubit_id)

    def free(self) -> None:
        """
        Unallocates the qubit.
        """
        self._conn._builder.add_qfree_commands(qubit_id=self.qubit_id)


class _FutureQubit(Qubit):
    def __init__(self, conn: BaseNetQASMConnection, future_id: Future):
        """Used by NetQASMConnection to handle operations on a future qubit (e.g. post createEPR)"""
        self._conn: BaseNetQASMConnection = conn

        self.qubit_id: Future = future_id

        self._activate()

    @property
    def entanglement_info(self) -> Optional[LinkLayerOKTypeK]:
        raise NotImplementedError(
            "Cannot access entanglement info of a future qubit yet"
        )

    @property
    def remote_entangled_node(self) -> Optional[str]:
        raise NotImplementedError(
            "Cannot access entanglement info of a future qubit yet"
        )
