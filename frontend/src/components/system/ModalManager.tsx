import { SlotDetailModal } from "../modals/SlotDetailModal";
import { ConfirmActionModal } from "../modals/ConfirmActionModal";
import { TaskDetailModal } from "../modals/TaskDetailModal";
import { SafetyAlarmModal } from "../modals/SafetyAlarmModal";
import { HardwareConfigModal } from "../modals/HardwareConfigModal";
import { InputSlotModal } from "../modals/InputSlotModal";
import type { DeviceInfo } from "../../types/drone";

export type ModalType =
  | "slot_detail"
  | "confirm_action"
  | "input_slot"
  | "task_detail"
  | "safety_alarm"
  | "hardware_config"
  | null;

interface Props {
  activeModal: ModalType;
  modalData?: any;
  devices?: DeviceInfo[];
  onRefreshDevices?: () => void;
  onClose: () => void;
  onConfirmAction?: (payload: any) => void;
  onResetEStop?: () => void;
}

export function ModalManager({
  activeModal,
  modalData,
  devices,
  onRefreshDevices,
  onClose,
  onConfirmAction,
  onResetEStop,
}: Props) {
  if (!activeModal) return null;

  return (
    <>
      <SlotDetailModal
        isOpen={activeModal === "slot_detail"}
        slotId={modalData?.slotId}
        productId={modalData?.productId}
        productName={modalData?.productName}
        status={modalData?.status}
        timeStored={modalData?.timeStored}
        missionRef={modalData?.missionRef}
        onClose={onClose}
        onPick={() => {
          onClose();
          if (onConfirmAction) {
            onConfirmAction({ action: "PICK", slotId: modalData?.slotId, cmd: "PICK", slot: modalData?.slotId });
          }
        }}
        onStore={() => {
          onClose();
          if (onConfirmAction) {
            onConfirmAction({ action: "STORE", slotId: modalData?.slotId, cmd: "STORE", slot: modalData?.slotId });
          }
        }}
      />

      <ConfirmActionModal
        isOpen={activeModal === "confirm_action"}
        title={modalData?.title}
        actionText={modalData?.actionText}
        productId={modalData?.productId}
        onCancel={onClose}
        onConfirm={() => {
          onClose();
          if (onConfirmAction) {
            onConfirmAction(modalData);
          }
        }}
      />

      <InputSlotModal
        isOpen={activeModal === "input_slot"}
        initialSlot={modalData?.slot || "B1"}
        onClose={onClose}
        onConfirm={(slot, taskType, note) => {
          onClose();
          if (onConfirmAction) {
            onConfirmAction({ action: taskType, slotId: slot, cmd: taskType, slot, note });
          }
        }}
      />

      <TaskDetailModal
        isOpen={activeModal === "task_detail"}
        taskId={modalData?.taskId}
        opType={modalData?.opType}
        target={modalData?.target}
        status={modalData?.status}
        progressPercent={modalData?.progressPercent}
        startTime={modalData?.startTime}
        etaTime={modalData?.etaTime}
        onClose={onClose}
      />

      <SafetyAlarmModal
        isOpen={activeModal === "safety_alarm"}
        reason={modalData?.reason || "Operator Pressed E-STOP"}
        onClose={onClose}
        onReset={() => {
          onClose();
          if (onResetEStop) {
            onResetEStop();
          }
        }}
      />

      <HardwareConfigModal
        isOpen={activeModal === "hardware_config"}
        devices={devices}
        onRefreshDevices={onRefreshDevices}
        onClose={onClose}
      />
    </>
  );
}
