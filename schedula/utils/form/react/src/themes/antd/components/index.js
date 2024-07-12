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
import Landing, {LandingTemplate} from './Landing'
import Landing_Banner0 from './Landing/Banner0'
import Landing_Banner1 from './Landing/Banner1'
import Landing_Banner2 from './Landing/Banner2'
import Landing_Banner3 from './Landing/Banner3'
import Landing_Banner4 from './Landing/Banner4'
import Landing_Banner5 from './Landing/Banner5'
import Landing_Contact0 from './Landing/Contact0'
import Landing_Content4 from './Landing/Content4'
import Landing_Content5 from './Landing/Content5'
import Landing_Content9 from './Landing/Content9'
import Landing_Content12 from './Landing/Content12'
import Landing_Content13 from './Landing/Content13'
import Landing_Feature0 from './Landing/Feature0'
import Landing_Feature1 from './Landing/Feature1'
import Landing_Feature2 from './Landing/Feature2'
import Landing_Feature3 from './Landing/Feature3'
import Landing_Feature4 from './Landing/Feature4'
import Landing_Feature5 from './Landing/Feature5'
import Landing_Feature6 from './Landing/Feature6'
import Landing_Feature7 from './Landing/Feature7'
import Landing_Feature8 from './Landing/Feature8'
import Landing_Footer0 from './Landing/Footer0'
import Landing_Footer1 from './Landing/Footer1'
import Landing_Footer2 from './Landing/Footer2'
import Landing_Point from './Landing/Point'
import Landing_Pricing0 from './Landing/Pricing0'
import Landing_Pricing1 from './Landing/Pricing1'
import Landing_Pricing2 from './Landing/Pricing2'
import Landing_Teams0 from './Landing/Teams0'
import Landing_Teams1 from './Landing/Teams1'
import Landing_Teams2 from './Landing/Teams2'
import Landing_Teams3 from './Landing/Teams3'

const Accordion = React.lazy(() => import('./Accordion'));
const Alert = React.lazy(() => import('./Alert'));
const App = React.lazy(() => import('./App'));
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
        Landing,
        LandingTemplate,
        "Landing.Banner0": Landing_Banner0,
        "Landing.Banner1": Landing_Banner1,
        "Landing.Banner2": Landing_Banner2,
        "Landing.Banner3": Landing_Banner3,
        "Landing.Banner4": Landing_Banner4,
        "Landing.Banner5": Landing_Banner5,
        "Landing.Contact0": Landing_Contact0,
        "Landing.Content4": Landing_Content4,
        "Landing.Content5": Landing_Content5,
        "Landing.Content9": Landing_Content9,
        "Landing.Content12": Landing_Content12,
        "Landing.Content13": Landing_Content13,
        "Landing.Feature0": Landing_Feature0,
        "Landing.Feature1": Landing_Feature1,
        "Landing.Feature2": Landing_Feature2,
        "Landing.Feature3": Landing_Feature3,
        "Landing.Feature4": Landing_Feature4,
        "Landing.Feature5": Landing_Feature5,
        "Landing.Feature6": Landing_Feature6,
        "Landing.Feature7": Landing_Feature7,
        "Landing.Feature8": Landing_Feature8,
        "Landing.Footer0": Landing_Footer0,
        "Landing.Footer1": Landing_Footer1,
        "Landing.Footer2": Landing_Footer2,
        "Landing.Point": Landing_Point,
        "Landing.Pricing0": Landing_Pricing0,
        "Landing.Pricing1": Landing_Pricing1,
        "Landing.Pricing2": Landing_Pricing2,
        "Landing.Teams0": Landing_Teams0,
        "Landing.Teams1": Landing_Teams1,
        "Landing.Teams2": Landing_Teams2,
        "Landing.Teams3": Landing_Teams3,
        Layout,
        "Layout.Content": Layout_Content,
        "Layout.Footer": Layout_Footer,
        "Layout.Header": Layout_Header,
        "Layout.Sider": Layout_Sider,
        List,
        "List.Item": List_Item,
        "List.Item.Meta": List_Item_Meta,
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