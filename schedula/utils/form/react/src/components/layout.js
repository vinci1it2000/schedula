import React from 'react';
import {getDefaultRegistry} from '@rjsf/core'
import _Markdown from './markdown';
import _Stepper from "./stepper";
import Submit from "./submit";
import _Tabs from "./tabs";
import _AppBar from "./nav";
import DataGrid from "./datagrid";
import Plot from "./plot";
import _Accordion from "./accordion";
import {JSONUpload, JSONExport} from "./io"
import {
    Accordion,
    AccordionActions,
    AccordionDetails,
    AccordionSummary,
    Alert,
    AlertTitle,
    AppBar,
    Autocomplete,
    Avatar,
    AvatarGroup,
    Backdrop,
    Badge,
    BottomNavigation,
    BottomNavigationAction,
    Box,
    Breadcrumbs,
    Button,
    ButtonBase,
    ButtonGroup,
    Card,
    CardActionArea,
    CardActions,
    CardContent,
    CardHeader,
    CardMedia,
    Checkbox,
    Chip,
    CircularProgress,
    ClickAwayListener,
    Collapse,
    Container,
    CssBaseline,
    Dialog,
    DialogActions,
    DialogContent,
    DialogContentText,
    DialogTitle,
    Divider,
    Drawer,
    Fab,
    Fade,
    FilledInput,
    FormControl,
    FormControlLabel,
    FormGroup,
    FormHelperText,
    FormLabel,
    GlobalStyles,
    Grid,
    Grow,
    Hidden,
    Icon,
    IconButton,
    ImageList,
    ImageListItem,
    ImageListItemBar,
    Input,
    InputAdornment,
    InputBase,
    InputLabel,
    LinearProgress,
    Link,
    List,
    ListItem,
    ListItemAvatar,
    ListItemButton,
    ListItemIcon,
    ListItemSecondaryAction,
    ListItemText,
    ListSubheader,
    Menu,
    MenuItem,
    MenuList,
    MobileStepper,
    Modal,
    NativeSelect,
    NoSsr,
    OutlinedInput,
    Pagination,
    PaginationItem,
    Paper,
    Popover,
    Popper,
    Portal,
    Radio,
    RadioGroup,
    Rating,
    ScopedCssBaseline,
    Select,
    Skeleton,
    Slide,
    Slider,
    Snackbar,
    SnackbarContent,
    SpeedDial,
    SpeedDialAction,
    SpeedDialIcon,
    Stack,
    Step,
    StepButton,
    StepConnector,
    StepContent,
    StepIcon,
    StepLabel,
    Stepper,
    StyledEngineProvider,
    SvgIcon,
    SwipeableDrawer,
    Switch,
    Tab,
    TabScrollButton,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableFooter,
    TableHead,
    TablePagination,
    TableRow,
    TableSortLabel,
    Tabs,
    TextField,
    TextareaAutosize,
    ToggleButton,
    ToggleButtonGroup,
    Toolbar,
    Tooltip,
    Typography,
    Unstable_Grid2,
    Unstable_TrapFocus,
    Zoom
} from '@mui/material';
import {
    ReflexContainer, ReflexSplitter, ReflexElement, ReflexHandle
} from 'react-reflex'
import {
    getUiOptions,
    orderProperties,
    ADDITIONAL_PROPERTY_FLAG,
    PROPERTIES_KEY
} from "@rjsf/utils";
import get from "lodash/get";
import has from "lodash/has";
import isObject from "lodash/isObject";

var components = {
    Suspense: React.Suspense,
    stepper: _Stepper,
    upload: JSONUpload,
    export: JSONExport,
    markdown: _Markdown,
    submit: Submit,
    appbar: _AppBar,
    tabs: _Tabs,
    datagrid: DataGrid,
    plot: Plot,
    accordion: _Accordion,
    Accordion,
    AccordionActions,
    AccordionDetails,
    AccordionSummary,
    Alert,
    AlertTitle,
    AppBar,
    Autocomplete,
    Avatar,
    AvatarGroup,
    Backdrop,
    Badge,
    BottomNavigation,
    BottomNavigationAction,
    Box,
    Breadcrumbs,
    Button,
    ButtonBase,
    ButtonGroup,
    Card,
    CardActionArea,
    CardActions,
    CardContent,
    CardHeader,
    CardMedia,
    Checkbox,
    Chip,
    CircularProgress,
    ClickAwayListener,
    Collapse,
    Container,
    CssBaseline,
    Dialog,
    DialogActions,
    DialogContent,
    DialogContentText,
    DialogTitle,
    Divider,
    Drawer,
    Fab,
    Fade,
    FilledInput,
    FormControl,
    FormControlLabel,
    FormGroup,
    FormHelperText,
    FormLabel,
    GlobalStyles,
    Grid,
    Grow,
    Hidden,
    Icon,
    IconButton,
    ImageList,
    ImageListItem,
    ImageListItemBar,
    Input,
    InputAdornment,
    InputBase,
    InputLabel,
    LinearProgress,
    Link,
    List,
    ListItem,
    ListItemAvatar,
    ListItemButton,
    ListItemIcon,
    ListItemSecondaryAction,
    ListItemText,
    ListSubheader,
    Menu,
    MenuItem,
    MenuList,
    MobileStepper,
    Modal,
    NativeSelect,
    NoSsr,
    OutlinedInput,
    Pagination,
    PaginationItem,
    Paper,
    Popover,
    Popper,
    Portal,
    Radio,
    RadioGroup,
    Rating,
    ScopedCssBaseline,
    Select,
    Skeleton,
    Slide,
    Slider,
    Snackbar,
    SnackbarContent,
    SpeedDial,
    SpeedDialAction,
    SpeedDialIcon,
    Stack,
    Step,
    StepButton,
    StepConnector,
    StepContent,
    StepIcon,
    StepLabel,
    Stepper,
    StyledEngineProvider,
    SvgIcon,
    SwipeableDrawer,
    Switch,
    Tab,
    TabScrollButton,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableFooter,
    TableHead,
    TablePagination,
    TableRow,
    TableSortLabel,
    Tabs,
    TextField,
    TextareaAutosize,
    ToggleButton,
    ToggleButtonGroup,
    Toolbar,
    Tooltip,
    Typography,
    Unstable_Grid2,
    Unstable_TrapFocus,
    Zoom,
    ReflexContainer,
    ReflexSplitter,
    ReflexElement,
    ReflexHandle
};


export function registerComponent(name, component) {
    components[name] = component
}

export function isEmpty(obj) {
    if (typeof (obj) === 'object') {
        if (Object.keys(obj).length === 0) {
            return true
        } else if (!Array.isArray(obj)) {
            return Object.values(obj).every(isEmpty)
        }
    }
    return undefined === obj
}

function compileFunc(func) {
    if (typeof func === 'string')
        return new Function("return " + func)()
    return func
}

class Layout extends React.Component {
    emptyObj = isEmpty
    createElement = (def) => {
        if (def.transformData)
            def = compileFunc(def.transformData)(this, def);
        let props = Object.assign({}, def.props || {}),
            children = [], type;
        [
            'onClick', 'onDoubleClick', 'onBlur', 'onFocus', 'onChange',
            'onError', 'onHover'
        ].forEach(k => {
            if (props.hasOwnProperty(k) && typeof props[k] === 'string')
                props[k] = compileFunc(props[k]).bind(this);
        })

        if (def.domain && !compileFunc(def.domain)(this, def, props))
            return null;
        Object.keys(props).forEach(k => {
            if (k.startsWith('children-')) {
                props[k] = props[k].map((c, index) => {
                        c.props = c.props || {}
                        c.props.key = index
                        return this.createElement(c)
                    }
                )
            }
        })
        if (props.hasOwnProperty('content')) {
            children = [props.content]
        } else if (def.values) {
            children = this.props.context.dataForm
        } else if (def.hasOwnProperty('value')) {
            children = [this.props.context.dataForm[def.value]]
        } else if (def.$id) {
            let element = this.props.context.render_key(def.$id, props);
            return Object.keys(element.props.schema).length ? element : null
        } else if (props.children) {
            children = props.children.map((c, index) => {
                    c.props = c.props || {}
                    c.props.key = index
                    return this.createElement(c)
                }
            )
        } else if (this.props.context.render_children) {
            children = this.props.context.render_children()
        }
        props.context = this.props.context
        children = children.filter(v => v !== null)
        type = components[def.component] || def.tag || "div"
        if (children.length) {
            return React.createElement(type, props, children)
        } else if (def.render_empty) {
            return React.createElement(type, props)
        } else {
            return null
        }
    };

    render() {
        return <React.Fragment>
            {this.createElement(this.props.root)}
        </React.Fragment>
    }
}


let {fields} = getDefaultRegistry();

function keyedToPlainFormData(keyedFormData) {
    if (Array.isArray(keyedFormData)) {
        return keyedFormData.map((keyedItem) => keyedItem.item);
    }
    return [];
}


export class ArrayField extends fields.ArrayField {
    render() {
        if (this.props.uiSchema['ui:layout']) {
            return React.createElement(Layout, {
                root: this.props.uiSchema['ui:layout'],
                context: this
            })
        } else {
            return super.render();
        }
    }

    render_children() {
        const {
            schema,
            uiSchema = {},
            errorSchema,
            idSchema,
            name,
            autofocus = false,
            registry,
            onBlur,
            onFocus,
            idPrefix,
            idSeparator = "_",
            rawErrors,
        } = this.props;
        const {keyedFormData} = this.state;
        const {schemaUtils} = registry;
        const _schemaItems = isObject(schema.items) ? (schema.items) : ({});
        const formData = keyedToPlainFormData(this.state.keyedFormData);
        return keyedFormData.length ? keyedFormData.map((keyedItem, index) => {
            const {key, item} = keyedItem;
            // While we are actually dealing with a single item of type T, the types require a T[], so cast
            const itemCast = item;
            const itemSchema = schemaUtils.retrieveSchema(_schemaItems, itemCast);
            const itemErrorSchema = errorSchema ? (errorSchema[index]) : undefined;
            const itemIdPrefix = idSchema.$id + idSeparator + index;
            const itemIdSchema = schemaUtils.toIdSchema(
                itemSchema,
                itemIdPrefix,
                itemCast,
                idPrefix,
                idSeparator
            );
            return this.renderArrayFieldItem({
                key,
                index,
                name: name && `${name}-${index}`,
                canMoveUp: index > 0,
                canMoveDown: index < formData.length - 1,
                itemSchema,
                itemIdSchema,
                itemErrorSchema,
                itemData: itemCast,
                itemUiSchema: uiSchema.items,
                autofocus: autofocus && index === 0,
                onBlur,
                onFocus,
                rawErrors,
            }).children;
        }) : [undefined]
    }
}


export class ObjectField extends fields.ObjectField {
    render() {
        if (this.props.uiSchema['ui:layout']) {
            return React.createElement(Layout, {
                root: this.props.uiSchema['ui:layout'],
                context: this
            })
        } else {
            return super.render();
        }
    }

    render_key(key, props) {
        const {
            schema: rawSchema,
            uiSchema = {},
            formData,
            errorSchema,
            idSchema,
            name,
            disabled = false,
            readonly = false,
            hideError,
            idPrefix,
            idSeparator,
            onBlur,
            onFocus,
            registry,
        } = this.props;

        const {fields, formContext, schemaUtils} = registry;
        const {SchemaField} = fields;
        const schema = schemaUtils.retrieveSchema(rawSchema, formData);

        const addedByAdditionalProperties = has(schema, [
            PROPERTIES_KEY,
            name,
            ADDITIONAL_PROPERTY_FLAG,
        ]);
        const fieldUiSchema = addedByAdditionalProperties
            ? uiSchema.additionalProperties
            : uiSchema[key];
        const fieldIdSchema = get(idSchema, [key], {});
        return (
            <SchemaField
                key={key}
                name={key}
                required={this.isRequired(key)}
                schema={get(schema, [PROPERTIES_KEY, key], {})}
                uiSchema={fieldUiSchema}
                errorSchema={get(errorSchema, key)}
                idSchema={fieldIdSchema}
                idPrefix={idPrefix}
                idSeparator={idSeparator}
                formData={get(formData, key)}
                formContext={formContext}
                wasPropertyKeyModified={this.state.wasPropertyKeyModified}
                onKeyChange={this.onKeyChange(key)}
                onChange={this.onPropertyChange(
                    key,
                    addedByAdditionalProperties
                )}
                onBlur={onBlur}
                onFocus={onFocus}
                registry={registry}
                disabled={disabled}
                readonly={readonly}
                hideError={hideError}
                onDropPropertyClick={this.onDropPropertyClick}
                {...props}
            />
        )
    };

    render_children() {
        const {
            schema: rawSchema,
            uiSchema = {},
            formData,
            registry,
        } = this.props;

        const {schemaUtils} = registry;
        const schema = schemaUtils.retrieveSchema(rawSchema, formData);
        const uiOptions = getUiOptions(uiSchema);
        const {properties: schemaProperties = {}} = schema;
        return orderProperties(Object.keys(schemaProperties), uiOptions.order).map(key => {
            return this.render_key(key)
        })
    }
}