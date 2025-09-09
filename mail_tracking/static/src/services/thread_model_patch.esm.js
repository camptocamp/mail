import {Record} from "@mail/core/common/record";
import {Thread} from "@mail/core/common/thread_model";
import "@mail/chatter/web_portal/thread_model_patch";
import {patch} from "@web/core/utils/patch";

patch(Thread.prototype, {
    setup() {
        super.setup();
        this.failedMessages = Record.many("Message", {
            compute() {
                return this.allMessages.filter(
                    (message) => message.failureNotifications.length > 0
                );
            },
        });
    },
    getFetchRoute() {
        if (this.model === "mail.box" && this.id === "failed") {
            return `/mail/failed/messages`;
        }
        return super.getFetchRoute(...arguments);
    },
});
