import {Record} from "@mail/core/common/record";
import {Message} from "@mail/core/common/message_model";
import {patch} from "@web/core/utils/patch";
import {createDocumentFragmentFromContent} from "@mail/utils/common/html";

patch(Message.prototype, {
    update(data) {
        console.log(
            "update:before",
            this,
            this.failureNotificationsNeedAction.length > 0,
            this.failureNotificationsNeedAction
        );
        console.log(data);
        super.update(data);
        console.log(
            "update:after",
            this,
            this.failureNotificationsNeedAction.length > 0,
            this.failureNotificationsNeedAction
        );
    },
    get failureNotificationsNeedAction() {
        return this.failureNotifications.filter(
            (notification) => notification.notification_status != "canceled"
        );
    },
    get hasUserFailureNotifications() {
        return this.isSelfAuthored && this.failureNotifications.length > 0;
    },
    get failedRecipients() {
        return this.partner_trackings;
    },
});
