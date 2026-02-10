/** @odoo-module **/

import { _lt } from "@web/core/l10n/translation";
import { Domain } from "@web/core/domain";
import { getActiveHotkey } from "@web/core/hotkeys/hotkey_service";
import { useActiveActions, useX2ManyCrud } from "@web/views/fields/relational_utils";
import { Many2XAutoCompleteCustom } from "@stock_api_assing/views/fields/relational_utils";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Many2ManyTagsField } from "@web/views/fields/many2many_tags/many2many_tags_field";
import { usePopover } from "@web/core/popover/popover_hook";
import { useService } from "@web/core/utils/hooks";

import { Component, useRef } from "@odoo/owl";

export class Many2ManyMultiField extends Component {
    setup() {
        this.orm = useService("orm");
        this.previousColorsMap = {};
        this.popover = usePopover();
        this.dialog = useService("dialog");
        this.dialogClose = [];

        this.autoCompleteRef = useRef("autoComplete");

        const { saveRecord, removeRecord } = useX2ManyCrud(() => this.props.value, true);

        this.activeActions = useActiveActions({
            fieldType: "many2many",
            crudOptions: {
                create: this.props.canCreate && this.props.createDomain,
                createEdit: this.props.canCreateEdit,
                onDelete: removeRecord,
            },
            getEvalParams: (props) => {
                return {
                    evalContext: this.evalContext,
                    readonly: props.readonly,
                };
            },
        });

        this.update = (recordlist) => {
            if (!recordlist) {
                return;
            }
            if (Array.isArray(recordlist)) {
                const resIds = recordlist.map((rec) => rec.id);
                return saveRecord(resIds);
            }
            return saveRecord(recordlist);
        };

        if (this.props.canQuickCreate) {
            this.quickCreate = async (name) => {
                const created = await this.orm.call(this.props.relation, "name_create", [name], {
                    context: this.context,
                });
                return saveRecord([created[0]]);
            };
        }

    }

    get domain() {
        return this.props.record.getFieldDomain(this.props.name);
    }
    get context() {
        return this.props.record.getFieldContext(this.props.name);
    }
    get evalContext() {
        return this.props.record.evalContext;
    }
    get string() {
        return this.props.record.activeFields[this.props.name].string;
    }

    getTagProps(record) {
        return {
            id: record.id, // datapoint_X
            resId: record.resId,
            text: record.data.display_name,
            colorIndex: record.data[this.props.colorField],
            onDelete: !this.props.readonly ? () => this.deleteTag(record.id) : undefined,
            onKeydown: this.onTagKeydown.bind(this),
        };
    }

    get tags() {
        return this.props.value.records.map((record) => this.getTagProps(record));
    }

    get showM2OSelectionField() {
        return !this.props.readonly;
    }

    deleteTag(id) {
        const tagRecord = this.props.value.records.find((record) => record.id === id);
        const ids = this.props.value.currentIds.filter((id) => id !== tagRecord.resId);
        this.props.value.replaceWith(ids);
    }

    getDomain() {
        return Domain.and([
            this.domain,
            Domain.not([["id", "in", this.props.value.currentIds]]),
        ]).toList(this.context);
    }

    focusTag(index) {
        const autoCompleteParent = this.autoCompleteRef.el.parentElement;
        const tags = autoCompleteParent.getElementsByClassName("badge");
        if (tags.length) {
            if (index === undefined) {
                tags[tags.length - 1].focus();
            } else {
                tags[index].focus();
            }
        }
    }

    onAutoCompleteKeydown(ev) {
        if (ev.isComposing) {
            // This case happens with an IME for example: we let it handle all key events.
            return;
        }
        const hotkey = getActiveHotkey(ev);
        const input = ev.target.closest(".o-autocomplete--input");
        const autoCompleteMenuOpened = !!this.autoCompleteRef.el.querySelector(
            ".o-autocomplete--dropdown-menu"
        );
        switch (hotkey) {
            case "arrowleft": {
                if (input.selectionStart || autoCompleteMenuOpened) {
                    return;
                }
                // focus rightmost tag if any.
                this.focusTag();
                break;
            }
            case "arrowright": {
                if (input.selectionStart !== input.value.length || autoCompleteMenuOpened) {
                    return;
                }
                // focus leftmost tag if any.
                this.focusTag(0);
                break;
            }
            case "backspace": {
                if (input.value) {
                    return;
                }
                const tags = this.tags;
                if (tags.length) {
                    const { id } = tags[tags.length - 1];
                    this.deleteTag(id);
                }
                break;
            }
            default:
                return;
        }
        ev.preventDefault();
        ev.stopPropagation();
    }

    onTagKeydown(ev) {
        if (this.props.readonly) {
            return;
        }
        const hotkey = getActiveHotkey(ev);
        const autoCompleteParent = this.autoCompleteRef.el.parentElement;
        const tags = [...autoCompleteParent.getElementsByClassName("badge")];
        const closestTag = ev.target.closest(".badge");
        const tagIndex = tags.indexOf(closestTag);
        const input = this.autoCompleteRef.el.querySelector(".o-autocomplete--input");
        switch (hotkey) {
            case "arrowleft": {
                if (tagIndex === 0) {
                    input.focus();
                } else {
                    this.focusTag(tagIndex - 1);
                }
                break;
            }
            case "arrowright": {
                if (tagIndex === tags.length - 1) {
                    input.focus();
                } else {
                    this.focusTag(tagIndex + 1);
                }
                break;
            }
            case "backspace": {
                input.focus();
                const { id } = this.tags[tagIndex] || {};
                this.deleteTag(id);
                break;
            }
            default:
                return;
        }
        ev.preventDefault();
        ev.stopPropagation();
    }

}

Many2ManyMultiField.template = "web.Many2ManyMultiField";
Many2ManyMultiField.components = {
    Many2ManyTagsField,
    Many2XAutoCompleteCustom,
};

Many2ManyMultiField.props = {
    ...standardFieldProps,
    canCreate: { type: Boolean, optional: true },
    canQuickCreate: { type: Boolean, optional: true },
    canCreateEdit: { type: Boolean, optional: true },
    colorField: { type: String, optional: true },
    createDomain: { type: [Array, Boolean], optional: true },
    placeholder: { type: String, optional: true },
    relation: { type: String },
    nameCreateField: { type: String, optional: true },
};
Many2ManyMultiField.defaultProps = {
    canCreate: true,
    canQuickCreate: true,
    canCreateEdit: true,
    nameCreateField: "name",
};

Many2ManyMultiField.displayName = _lt("Tags");
Many2ManyMultiField.supportedTypes = ["many2many"];
Many2ManyMultiField.fieldsToFetch = {
    display_name: { name: "display_name", type: "char" },
};
Many2ManyMultiField.isSet = (value) => value.count > 0;

Many2ManyMultiField.extractProps = ({ attrs, field }) => {
    const hasCreatePermission = attrs.can_create ? Boolean(JSON.parse(attrs.can_create)) : true;

    const noCreate = Boolean(attrs.options.no_create);
    const canCreate = hasCreatePermission && !noCreate;
    const noQuickCreate = Boolean(attrs.options.no_quick_create);
    const noCreateEdit = Boolean(attrs.options.no_create_edit);

    return {
        colorField: attrs.options.color_field,
        nameCreateField: attrs.options.create_name_field,
        relation: field.relation,
        canCreate,
        canQuickCreate: canCreate && !noQuickCreate,
        canCreateEdit: canCreate && !noCreateEdit,
        createDomain: attrs.options.create,
        placeholder: attrs.placeholder,
    };
};

registry.category("fields").add("many2many_multi", Many2ManyMultiField);