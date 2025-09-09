import {patch} from "@web/core/utils/patch";
import {MailCoreWeb} from "@mail/core/common/mail_core_web_service";

patch(MailCoreCommon.prototype, {
    setup() {
        super.setup();
        this.env.bus.addEventListener(
            "mail.message/delete",
            ({detail: {message, notifId}}) => {
                if (
                    message.hasUserFailureNotifications &&
                    notifId > this.store.failed.counter_bus_id
                ) {
                    this.store.failed.counter--;
                }
            }
        );
        this.busService.subscribe("mail.record/insert", (payload) => {
            this.store.insert(payload, {html: true});
        });
        this.busService.subscribe(
            "mail.tracking/set_need_action_done",
            (payload, metadata) => {
                const {id: notifId} = metadata;
                const {message_ids: messageIds} = payload;
                for (const id of messageIds) {
                    const message = this.store.Message.get({id});
                    const failedBox = this.store.failed;
                    if (notifId > failedBox.counter_bus_id) {
                        failedBox.counter--;
                    }
                    failedBox.messages.delete(message);
                    message.delete();
                }
            }
        );
    },
});
