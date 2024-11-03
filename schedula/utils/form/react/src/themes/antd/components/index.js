import React from "react";
import {registerComponent, registerComponentDomain} from "../../../core";
import {
    generateComponents as coreGenerateComponents
} from "../../../core/components";
import {
    generateComponentsDomains as coreGenerateComponentsDomains
} from "../../../core/components";
import {domainDebug} from './Debug'
import {domainErrors} from "./Errors";

const Accordion = React.lazy(() => import('./Accordion'));
const Alert = React.lazy(() => import('./Alert'));
const App = React.lazy(() => import('./App'));
const App_Contact = React.lazy(() => import('./App/Contact'));
const App_Language = React.lazy(() => import('./App/Language'));
const App_User = React.lazy(() => import('./App/User'));
const App_User_Change = React.lazy(() => import('./App/User/Change'));
const App_User_Confirm = React.lazy(() => import('./App/User/Confirm'));
const App_User_Forgot = React.lazy(() => import('./App/User/Forgot'));
const App_User_Info = React.lazy(() => import('./App/User/Info'));
const App_User_Login = React.lazy(() => import('./App/User/Login'));
const App_User_Logout = React.lazy(() => import('./App/User/Logout'));
const App_User_Register = React.lazy(() => import('./App/User/Register'));
const App_User_Reset = React.lazy(() => import('./App/User/Reset'));
const App_User_Settings = React.lazy(() => import('./App/User/Settings'));
const ArrayAccordion = React.lazy(() => import('./ArrayAccordion'));
const ArrayCopy = React.lazy(() => import('./ArrayCopy'));
const Avatar = React.lazy(() => import('./Avatar'));
const Avatar_Group = React.lazy(() => import('./Avatar/Group'));
const Badge = React.lazy(() => import('./Badge'));
const Badge_Ribbon = React.lazy(() => import('./Badge/Ribbon'));
const Button = React.lazy(() => import('./Button'));
const Card = React.lazy(() => import('./Card'));
const Card_Grid = React.lazy(() => import('./Card/Grid'));
const Card_Meta = React.lazy(() => import('./Card/Meta'));
const Carousel = React.lazy(() => import('./Carousel'));
const Collapse = React.lazy(() => import('./Collapse'));
const Collapse_Panel = React.lazy(() => import('./Collapse/Panel'));
const Cookies = React.lazy(() => import('./Cookies'));
const Debug = React.lazy(() => import('./Debug'));
const Descriptions = React.lazy(() => import('./Descriptions'));
const Descriptions_Item = React.lazy(() => import('./Descriptions/Item'));
const Divider = React.lazy(() => import('./Divider'));
const Drawer = React.lazy(() => import('./Drawer'));
const Errors = React.lazy(() => import('./Errors'));
const Errors_Drawer = React.lazy(() => import('./Errors/Drawer'));
const Export = React.lazy(() => import('./Export'));
const Flex = React.lazy(() => import('./Flex'));
const FloatButton = React.lazy(() => import('./FloatButton'));
const Grid_Col = React.lazy(() => import('./Grid/Col'));
const Grid_Row = React.lazy(() => import('./Grid/Row'));
const Icon = React.lazy(() => import('./Icon'));
const Image_PreviewGroup = React.lazy(() => import('./Image/PreviewGroup'));
const Import = React.lazy(() => import('./Import'));
const Layout = React.lazy(() => import('./Layout'));
const Layout_Content = React.lazy(() => import('./Layout/Content'));
const Layout_Footer = React.lazy(() => import('./Layout/Footer'));
const Layout_Header = React.lazy(() => import('./Layout/Header'));
const Layout_Sider = React.lazy(() => import('./Layout/Sider'));
const List = React.lazy(() => import('./List'));
const List_Item = React.lazy(() => import('./List/Item'));
const List_Item_Meta = React.lazy(() => import('./List/Item/Meta'));
const Locale = React.lazy(() => import('./Locale'));
const Markdown = React.lazy(() => import('./Markdown'));
const OverPack = React.lazy(() => import('./OverPack'));
const Popconfirm = React.lazy(() => import('./Popconfirm'));
const Popover = React.lazy(() => import('./Popover'));
const Pricing = React.lazy(() => import('./Pricing'));
const Progress = React.lazy(() => import('./Progress'));
const QueueAnim = React.lazy(() => import('./QueueAnim'));
const Result = React.lazy(() => import('./Result'));
const Segmented = React.lazy(() => import('./Segmented'));
const Skeleton = React.lazy(() => import('./Skeleton'));
const Space = React.lazy(() => import('./Space'));
const Space_Compact = React.lazy(() => import('./Space/Compact'));
const Spin = React.lazy(() => import('./Spin'));
const Splitter = React.lazy(() => import('./Splitter'));
const Splitter_Panel = React.lazy(() => import('./Splitter/Panel'));
const Steps = React.lazy(() => import('./Steps'));
const Stripe_Card = React.lazy(() => import('./Stripe/card'));
const Stripe_Cards = React.lazy(() => import('./Stripe/cards'));
const Submit = React.lazy(() => import('./Submit'));
const Submit_Debug = React.lazy(() => import('./Submit/Debug'));
const Table = React.lazy(() => import('./Table'));
const Table_Summary = React.lazy(() => import('./Table/Summary'));
const Table_Summary_Col = React.lazy(() => import('./Table/Summary/Col'));
const Table_Summary_Row = React.lazy(() => import('./Table/Summary/Row'));
const Tabs = React.lazy(() => import('./Tabs'));
const Tag = React.lazy(() => import('./Tag'));
const Timeline = React.lazy(() => import('./Timeline'));
const Tooltip = React.lazy(() => import('./Tooltip'));
const Tour = React.lazy(() => import('./Tour'));
const TweenOne = React.lazy(() => import('./TweenOne'));
const Typography_Paragraph = React.lazy(() => import('./Typography/Paragraph'));
const Typography_Text = React.lazy(() => import('./Typography/Text'));
const Typography_Title = React.lazy(() => import('./Typography/Title'));
const Watermark = React.lazy(() => import('./Watermark'));


export function generateComponents(register = true, registerDomains = true) {
    const components = {
        ...coreGenerateComponents(),
        Accordion,
        Alert,
        App,
        "App.Contact": App_Contact,
        "App.Language": App_Language,
        "App.User": App_User,
        "App.User.Change": App_User_Change,
        "App.User.Confirm": App_User_Confirm,
        "App.User.Forgot": App_User_Forgot,
        "App.User.Info": App_User_Info,
        "App.User.Login": App_User_Login,
        "App.User.Logout": App_User_Logout,
        "App.User.Register": App_User_Register,
        "App.User.Reset": App_User_Reset,
        "App.User.Settings": App_User_Settings,
        ArrayAccordion,
        ArrayCopy,
        Avatar,
        "Avatar.Group": Avatar_Group,
        Badge,
        "Badge.Ribbon": Badge_Ribbon,
        Button,
        Card,
        "Card.Grid": Card_Grid,
        "Card.Meta": Card_Meta,
        Carousel,
        Collapse,
        "Collapse.Panel": Collapse_Panel,
        Cookies,
        Debug,
        Descriptions,
        "Descriptions.Item": Descriptions_Item,
        Divider,
        Drawer,
        Errors,
        "Errors.Drawer": Errors_Drawer,
        Export,
        Flex,
        FloatButton,
        "Grid.Col": Grid_Col,
        "Grid.Row": Grid_Row,
        Icon,
        "Image.PreviewGroup": Image_PreviewGroup,
        Import,
        Layout,
        "Layout.Content": Layout_Content,
        "Layout.Footer": Layout_Footer,
        "Layout.Header": Layout_Header,
        "Layout.Sider": Layout_Sider,
        List,
        "List.Item": List_Item,
        "List.Item.Meta": List_Item_Meta,
        Locale,
        Markdown,
        OverPack,
        Popconfirm,
        Popover,
        Pricing,
        Progress,
        QueueAnim,
        Result,
        Segmented,
        Skeleton,
        Space,
        "Space.Compact": Space_Compact,
        Spin,
        Splitter,
        "Splitter.Panel": Splitter_Panel,
        Steps,
        "Stripe.Card": Stripe_Card,
        "Stripe.Cards": Stripe_Cards,
        Submit,
        "Submit.Debug": Submit_Debug,
        Table,
        "Table.Summary": Table_Summary,
        "Table.Summary.Col": Table_Summary_Col,
        "Table.Summary.Row": Table_Summary_Row,
        Tabs,
        Tag,
        Timeline,
        Tooltip,
        Tour,
        TweenOne,
        "Typography.Paragraph": Typography_Paragraph,
        "Typography.Text": Typography_Text,
        "Typography.Title": Typography_Title,
        Watermark
    };
    const domains = {
        ...coreGenerateComponentsDomains(),
        Debug: domainDebug,
        Errors: domainErrors
    }
    if (register)
        Object.entries(components).forEach(([name, component]) => {
            registerComponent(name, component)
            if (registerDomains && name in domains) {
                registerComponentDomain(name, domains[name])
            }
        })
    return components
}

export default generateComponents();