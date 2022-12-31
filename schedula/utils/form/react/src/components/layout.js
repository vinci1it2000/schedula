import React, {Suspense} from "react";
import {getDefaultRegistry} from '@rjsf/core'
import {
    getUiOptions,
    orderProperties,
    ADDITIONAL_PROPERTY_FLAG,
    PROPERTIES_KEY
} from "@rjsf/utils";
import get from "lodash/get";
import has from "lodash/has";
import isObject from "lodash/isObject";
import {
    ReflexContainer, ReflexSplitter, ReflexElement, ReflexHandle
} from 'react-reflex'

const _Markdown = React.lazy(() => import('./markdown'));
const _Stepper = React.lazy(() => import("./stepper"));
const Submit = React.lazy(() => import("./submit"));
const _Tabs = React.lazy(() => import("./tabs"));
const _AppBar = React.lazy(() => import("./nav"));
const DataGrid = React.lazy(() => import("./datagrid"));
const Plot = React.lazy(() => import("./plot"));
const _Accordion = React.lazy(() => import("./accordion"));
const {JSONUpload, JSONExport} = React.lazy(() => import("./io"));
const Accordion = React.lazy(() => import('@mui/material/Accordion'));
const AccordionActions = React.lazy(() => import('@mui/material/AccordionActions'));
const AccordionDetails = React.lazy(() => import('@mui/material/AccordionDetails'));
const AccordionSummary = React.lazy(() => import('@mui/material/AccordionSummary'));
const Alert = React.lazy(() => import('@mui/material/Alert'));
const AlertTitle = React.lazy(() => import('@mui/material/AlertTitle'));
const AppBar = React.lazy(() => import('@mui/material/AppBar'));
const Autocomplete = React.lazy(() => import('@mui/material/Autocomplete'));
const Avatar = React.lazy(() => import('@mui/material/Avatar'));
const AvatarGroup = React.lazy(() => import('@mui/material/AvatarGroup'));
const Backdrop = React.lazy(() => import('@mui/material/Backdrop'));
const Badge = React.lazy(() => import('@mui/material/Badge'));
const BottomNavigation = React.lazy(() => import('@mui/material/BottomNavigation'));
const BottomNavigationAction = React.lazy(() => import('@mui/material/BottomNavigationAction'));
const Box = React.lazy(() => import('@mui/material/Box'));
const Breadcrumbs = React.lazy(() => import('@mui/material/Breadcrumbs'));
const Button = React.lazy(() => import('@mui/material/Button'));
const ButtonBase = React.lazy(() => import('@mui/material/ButtonBase'));
const ButtonGroup = React.lazy(() => import('@mui/material/ButtonGroup'));
const Card = React.lazy(() => import('@mui/material/Card'));
const CardActionArea = React.lazy(() => import('@mui/material/CardActionArea'));
const CardActions = React.lazy(() => import('@mui/material/CardActions'));
const CardContent = React.lazy(() => import('@mui/material/CardContent'));
const CardHeader = React.lazy(() => import('@mui/material/CardHeader'));
const CardMedia = React.lazy(() => import('@mui/material/CardMedia'));
const Checkbox = React.lazy(() => import('@mui/material/Checkbox'));
const Chip = React.lazy(() => import('@mui/material/Chip'));
const CircularProgress = React.lazy(() => import('@mui/material/CircularProgress'));
const ClickAwayListener = React.lazy(() => import('@mui/material/ClickAwayListener'));
const Collapse = React.lazy(() => import('@mui/material/Collapse'));
const Container = React.lazy(() => import('@mui/material/Container'));
const CssBaseline = React.lazy(() => import('@mui/material/CssBaseline'));
const Dialog = React.lazy(() => import('@mui/material/Dialog'));
const DialogActions = React.lazy(() => import('@mui/material/DialogActions'));
const DialogContent = React.lazy(() => import('@mui/material/DialogContent'));
const DialogContentText = React.lazy(() => import('@mui/material/DialogContentText'));
const DialogTitle = React.lazy(() => import('@mui/material/DialogTitle'));
const Divider = React.lazy(() => import('@mui/material/Divider'));
const Drawer = React.lazy(() => import('@mui/material/Drawer'));
const Fab = React.lazy(() => import('@mui/material/Fab'));
const Fade = React.lazy(() => import('@mui/material/Fade'));
const FilledInput = React.lazy(() => import('@mui/material/FilledInput'));
const FormControl = React.lazy(() => import('@mui/material/FormControl'));
const FormControlLabel = React.lazy(() => import('@mui/material/FormControlLabel'));
const FormGroup = React.lazy(() => import('@mui/material/FormGroup'));
const FormHelperText = React.lazy(() => import('@mui/material/FormHelperText'));
const FormLabel = React.lazy(() => import('@mui/material/FormLabel'));
const GlobalStyles = React.lazy(() => import('@mui/material/GlobalStyles'));
const Grid = React.lazy(() => import('@mui/material/Grid'));
const Grow = React.lazy(() => import('@mui/material/Grow'));
const Hidden = React.lazy(() => import('@mui/material/Hidden'));
const Icon = React.lazy(() => import('@mui/material/Icon'));
const IconButton = React.lazy(() => import('@mui/material/IconButton'));
const ImageList = React.lazy(() => import('@mui/material/ImageList'));
const ImageListItem = React.lazy(() => import('@mui/material/ImageListItem'));
const ImageListItemBar = React.lazy(() => import('@mui/material/ImageListItemBar'));
const Input = React.lazy(() => import('@mui/material/Input'));
const InputAdornment = React.lazy(() => import('@mui/material/InputAdornment'));
const InputBase = React.lazy(() => import('@mui/material/InputBase'));
const InputLabel = React.lazy(() => import('@mui/material/InputLabel'));
const LinearProgress = React.lazy(() => import('@mui/material/LinearProgress'));
const Link = React.lazy(() => import('@mui/material/Link'));
const List = React.lazy(() => import('@mui/material/List'));
const ListItem = React.lazy(() => import('@mui/material/ListItem'));
const ListItemAvatar = React.lazy(() => import('@mui/material/ListItemAvatar'));
const ListItemButton = React.lazy(() => import('@mui/material/ListItemButton'));
const ListItemIcon = React.lazy(() => import('@mui/material/ListItemIcon'));
const ListItemSecondaryAction = React.lazy(() => import('@mui/material/ListItemSecondaryAction'));
const ListItemText = React.lazy(() => import('@mui/material/ListItemText'));
const ListSubheader = React.lazy(() => import('@mui/material/ListSubheader'));
const Menu = React.lazy(() => import('@mui/material/Menu'));
const MenuItem = React.lazy(() => import('@mui/material/MenuItem'));
const MenuList = React.lazy(() => import('@mui/material/MenuList'));
const MobileStepper = React.lazy(() => import('@mui/material/MobileStepper'));
const Modal = React.lazy(() => import('@mui/material/Modal'));
const NativeSelect = React.lazy(() => import('@mui/material/NativeSelect'));
const NoSsr = React.lazy(() => import('@mui/material/NoSsr'));
const OutlinedInput = React.lazy(() => import('@mui/material/OutlinedInput'));
const Pagination = React.lazy(() => import('@mui/material/Pagination'));
const PaginationItem = React.lazy(() => import('@mui/material/PaginationItem'));
const Paper = React.lazy(() => import('@mui/material/Paper'));
const Popover = React.lazy(() => import('@mui/material/Popover'));
const Popper = React.lazy(() => import('@mui/material/Popper'));
const Portal = React.lazy(() => import('@mui/material/Portal'));
const Radio = React.lazy(() => import('@mui/material/Radio'));
const RadioGroup = React.lazy(() => import('@mui/material/RadioGroup'));
const Rating = React.lazy(() => import('@mui/material/Rating'));
const ScopedCssBaseline = React.lazy(() => import('@mui/material/ScopedCssBaseline'));
const Select = React.lazy(() => import('@mui/material/Select'));
const Skeleton = React.lazy(() => import('@mui/material/Skeleton'));
const Slide = React.lazy(() => import('@mui/material/Slide'));
const Slider = React.lazy(() => import('@mui/material/Slider'));
const Snackbar = React.lazy(() => import('@mui/material/Snackbar'));
const SnackbarContent = React.lazy(() => import('@mui/material/SnackbarContent'));
const SpeedDial = React.lazy(() => import('@mui/material/SpeedDial'));
const SpeedDialAction = React.lazy(() => import('@mui/material/SpeedDialAction'));
const SpeedDialIcon = React.lazy(() => import('@mui/material/SpeedDialIcon'));
const Stack = React.lazy(() => import('@mui/material/Stack'));
const Step = React.lazy(() => import('@mui/material/Step'));
const StepButton = React.lazy(() => import('@mui/material/StepButton'));
const StepConnector = React.lazy(() => import('@mui/material/StepConnector'));
const StepContent = React.lazy(() => import('@mui/material/StepContent'));
const StepIcon = React.lazy(() => import('@mui/material/StepIcon'));
const StepLabel = React.lazy(() => import('@mui/material/StepLabel'));
const Stepper = React.lazy(() => import('@mui/material/Stepper'));
const StyledEngineProvider = React.lazy(() => import('@mui/material/StyledEngineProvider'));
const SvgIcon = React.lazy(() => import('@mui/material/SvgIcon'));
const SwipeableDrawer = React.lazy(() => import('@mui/material/SwipeableDrawer'));
const Switch = React.lazy(() => import('@mui/material/Switch'));
const Tab = React.lazy(() => import('@mui/material/Tab'));
const TabScrollButton = React.lazy(() => import('@mui/material/TabScrollButton'));
const Table = React.lazy(() => import('@mui/material/Table'));
const TableBody = React.lazy(() => import('@mui/material/TableBody'));
const TableCell = React.lazy(() => import('@mui/material/TableCell'));
const TableContainer = React.lazy(() => import('@mui/material/TableContainer'));
const TableFooter = React.lazy(() => import('@mui/material/TableFooter'));
const TableHead = React.lazy(() => import('@mui/material/TableHead'));
const TablePagination = React.lazy(() => import('@mui/material/TablePagination'));
const TableRow = React.lazy(() => import('@mui/material/TableRow'));
const TableSortLabel = React.lazy(() => import('@mui/material/TableSortLabel'));
const Tabs = React.lazy(() => import('@mui/material/Tabs'));
const TextField = React.lazy(() => import('@mui/material/TextField'));
const TextareaAutosize = React.lazy(() => import('@mui/material/TextareaAutosize'));
const ToggleButton = React.lazy(() => import('@mui/material/ToggleButton'));
const ToggleButtonGroup = React.lazy(() => import('@mui/material/ToggleButtonGroup'));
const Toolbar = React.lazy(() => import('@mui/material/Toolbar'));
const Tooltip = React.lazy(() => import('@mui/material/Tooltip'));
const Typography = React.lazy(() => import('@mui/material/Typography'));
const Unstable_Grid2 = React.lazy(() => import('@mui/material/Unstable_Grid2'));
const Unstable_TrapFocus = React.lazy(() => import('@mui/material/Unstable_TrapFocus'));
const Zoom = React.lazy(() => import('@mui/material/Zoom'));

var components = {
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
    ReflexContainer: ReflexContainer,
    ReflexSplitter: ReflexSplitter,
    ReflexElement: ReflexElement,
    ReflexHandle: ReflexHandle
};


export function registerComponent(name, component) {
    components[name] = component
}

export function isEmpty(obj) {
    if (typeof (obj) === 'object') {
        if (obj === null || Object.keys(obj).length === 0) {
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
        } else if (def.hasOwnProperty('path')) {
            children = [get(this.props, def.path)]
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
        return <Suspense>
            {this.createElement(this.props.root)}
        </Suspense>
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